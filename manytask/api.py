from __future__ import annotations

import functools
import logging
import secrets
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Callable, TypeVar

import yaml
from flask import Blueprint, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue
from enum import Enum
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, NoResultFound

from manytask.abstract import RmsApiException, StorageApi
from manytask.database import TaskDisabledError

from .abstract import RmsApi, RmsUser
from .auth import requires_auth, requires_ready
from .config import (
    AddUserToNamespaceRequest,
    CourseResponse,
    CreateCourseRequest,
    CreateNamespaceRequest,
    ErrorResponse,
    ManytaskGroupConfig,
    ManytaskTaskConfig,
    ManytaskUpdateDatabasePayload,
    NamespaceListResponse,
    NamespaceResponse,
    NamespaceUserItem,
    NamespaceUsersListResponse,
    NamespaceWithRoleResponse,
    UpdateUserRoleRequest,
    UserOnNamespaceResponse,
)
from pydantic import BaseModel
from .course import DEFAULT_TIMEZONE, Course, CourseStatus, get_current_time
from .main import CustomFlask
from .utils.database import get_database_table_data
from .utils.generic import sanitize_and_validate_comment, sanitize_log_data


logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api/<course_name>")
namespace_bp = Blueprint("namespace_api", __name__, url_prefix="/api")


def __get_course_or_not_found(storage_api: StorageApi, course_name: str) -> Course:
    course = storage_api.get_course(course_name)
    if course is None:
        logger.warning("Course not found: %s", course_name)
        abort(HTTPStatus.NOT_FOUND, "Course not found")
    return course


T = TypeVar("T", bound=BaseModel)


def validate_json_request(model_class: type[T]) -> tuple[T | None, ResponseReturnValue | None]:
    """Validate JSON request with Pydantic model (helper function).

    Returns:
        Tuple of (validated_data, error_response).
        If validation succeeds: (data, None)
        If validation fails: (None, error_response)
    """
    if not request.is_json:
        return None, (jsonify(ErrorResponse(error="Request must be JSON").model_dump()), HTTPStatus.BAD_REQUEST)

    try:
        data = model_class.model_validate(request.get_json())
        return data, None
    except ValidationError as exc:
        logger.warning("Invalid request payload: %s", exc.errors())
        return None, (
            jsonify(ErrorResponse(error=f"Invalid request data: {exc.errors()}").model_dump()),
            HTTPStatus.BAD_REQUEST,
        )


def requires_json_validation(model_class: type[BaseModel]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate JSON request with Pydantic model.

    The validated data will be passed to the function via 'validated_data' kwarg.
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            validated_data, error = validate_json_request(model_class)
            if error:
                return error

            kwargs["validated_data"] = validated_data
            return f(*args, **kwargs)

        return decorated

    return decorator


def requires_namespace_admin(
    return_404_if_not_found: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to check if user has admin access to namespace (Instance Admin or Namespace Admin).

    The decorated function must have 'namespace_id' parameter.
    The namespace object will be passed to the function via 'namespace' kwarg.

    Args:
        return_404_if_not_found: If True, returns 404 for non-existent namespace (for POST/PUT/DELETE).
                                 If False, returns 403 for security by obscurity (for GET).
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            app: CustomFlask = current_app  # type: ignore
            storage_api = app.storage_api

            namespace_id = kwargs.get("namespace_id")
            if namespace_id is None:
                logger.error("requires_namespace_admin decorator used on function without namespace_id parameter")
                return jsonify(
                    ErrorResponse(error="Internal server error").model_dump()
                ), HTTPStatus.INTERNAL_SERVER_ERROR

            rms_id = session["rms"]["rms_id"]
            username = session["auth"]["username"]
            is_instance_admin = storage_api.check_if_instance_admin(rms_id)

            if not is_instance_admin:
                try:
                    namespace, user_role = storage_api.get_namespace_by_id(namespace_id, rms_id)
                    if user_role != "namespace_admin":
                        logger.warning(
                            "User %s (role=%s) attempted to access namespace id=%s without admin privileges",
                            username,
                            user_role,
                            namespace_id,
                        )
                        return jsonify(
                            ErrorResponse(
                                error="Only Instance Admin or Namespace Admin can perform this action"
                            ).model_dump()
                        ), HTTPStatus.FORBIDDEN
                except PermissionError:
                    logger.warning("User %s attempted to access namespace id=%s without access", username, namespace_id)
                    return jsonify(ErrorResponse(error="Access denied").model_dump()), HTTPStatus.FORBIDDEN
            else:
                try:
                    namespace, _ = storage_api.get_namespace_by_id(namespace_id, rms_id)
                except (PermissionError, NoResultFound):
                    logger.warning("Namespace id=%s not found", namespace_id)
                    if return_404_if_not_found:
                        return jsonify(ErrorResponse(error="Namespace not found").model_dump()), HTTPStatus.NOT_FOUND
                    else:
                        return jsonify(ErrorResponse(error="Access denied").model_dump()), HTTPStatus.FORBIDDEN

            kwargs["namespace"] = namespace
            return f(*args, **kwargs)

        return decorated

    return decorator


def requires_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        course_name = kwargs["course_name"]

        logger.debug("Checking token for course=%s", course_name)

        course = __get_course_or_not_found(app.storage_api, course_name)

        course_token = course.token
        token = request.form.get("token", request.headers.get("Authorization", ""))
        if not token or not course_token:
            logger.warning("Missing token for course=%s", course_name)
            abort(HTTPStatus.FORBIDDEN)
        token = token.split()[-1]
        if not secrets.compare_digest(token, course_token):
            logger.warning("Invalid token for course=%s", course_name)
            abort(HTTPStatus.FORBIDDEN)

        logger.debug("Token validated for course=%s", course_name)
        return f(*args, **kwargs)

    return decorated


class AuthMethod(Enum):
    COURSE_TOKEN = "course_token"
    SESSION = "session"


def requires_auth_or_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "Authorization" in request.headers:
            return requires_token(f)(*args, **kwargs, auth_method=AuthMethod.COURSE_TOKEN)
        else:
            return requires_auth(f)(*args, **kwargs, auth_method=AuthMethod.SESSION)

    return decorated


def _parse_flags(flags: str | None) -> timedelta:
    flags = flags or ""

    extra_time = timedelta()
    left_colon = flags.find(":")
    right_colon = flags.find(":", left_colon + 1)
    if right_colon > -1 and left_colon > 0:
        parsed = None
        date_string = flags[right_colon + 1 :]
        try:
            parsed = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=DEFAULT_TIMEZONE)
        except ValueError:
            logger.error("Could not parse date from flag %s", flags)
        if parsed is not None and get_current_time() <= parsed:
            days = int(flags[left_colon + 1 : right_colon])
            extra_time = timedelta(days=days)
            logger.debug("Parsed extra_time=%s from flags=%s", extra_time, flags)
    return extra_time


# ruff: noqa PLR0913
def _update_score(
    course: Course,
    group: ManytaskGroupConfig,
    task: ManytaskTaskConfig,
    score: int,
    flags: str,
    old_score: int,
    submit_time: datetime,
    check_deadline: bool = True,
    allow_reduction: bool = False,
) -> int:
    logger.debug(
        f"Update score: task={task.name}, old_score={old_score}, new_score={score}, "
        f"flags={flags}, submit_time={submit_time}, check_deadline={check_deadline}"
    )
    if old_score < 0:
        return old_score

    if check_deadline:
        extra_time = _parse_flags(flags)

        multiplier = group.get_current_percent_multiplier(
            now=submit_time - extra_time,
            deadlines_type=course.deadlines_type,
        )
        score = int(score * multiplier)
        logger.debug("Applied multiplier=%s, adjusted_score=%s", multiplier, score)

    return score if allow_reduction else max(old_score, score)


@bp.get("/healthcheck")
@requires_ready
def healthcheck() -> ResponseReturnValue:
    return "OK", HTTPStatus.OK


def _validate_and_extract_params(
    form_data: dict[str, Any], rms_api: RmsApi, storage_api: StorageApi, course_name: str
) -> tuple[RmsUser, Course, ManytaskTaskConfig, ManytaskGroupConfig]:
    """Validate and extract parameters from form data."""

    if "user_id" in form_data and "username" in form_data:
        abort(HTTPStatus.BAD_REQUEST, "Both `user_id` or `username` were provided, use only one")
    elif "user_id" in form_data:
        try:
            user_id = form_data["user_id"]
            rms_user = rms_api.get_rms_user_by_id(user_id)
            logger.info("Found user by id=%s: %s", user_id, rms_user.username)
        except RmsApiException:
            abort(HTTPStatus.NOT_FOUND, f"There is no student with user ID {user_id}")
    elif "username" in form_data:
        try:
            username = form_data["username"]
            rms_user = rms_api.get_rms_user_by_username(username)
        except RmsApiException:
            abort(HTTPStatus.NOT_FOUND, f"There is no student with username {username}")
    else:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required attribute `user_id` or `username`")

    if "task" not in form_data:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required attribute `task`")
    task_name = form_data["task"]

    try:
        course, group, task = storage_api.find_task(course_name, task_name)
    except (KeyError, TaskDisabledError):
        logger.warning("Task not found or disabled: %s", sanitize_log_data(task_name))
        abort(HTTPStatus.NOT_FOUND, f"There is no task with name `{task_name}` (or it is closed for submission)")

    return rms_user, course, task, group


def _process_submit_time(submit_time_str: str | None, now_with_timezone: datetime) -> datetime:
    """Process and validate submit time."""
    submit_time = None
    if submit_time_str:
        try:
            submit_time = datetime.strptime(submit_time_str, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            logger.warning("Invalid submit_time format: %s", sanitize_log_data(submit_time_str))
            submit_time = None

    submit_time = submit_time or now_with_timezone
    submit_time.replace(tzinfo=now_with_timezone.tzinfo)
    return submit_time


def _process_score(form_data: dict[str, Any], task_score: int) -> int | None:
    """Process and validate score from form data."""
    if "score" not in form_data:
        logger.debug("No score provided, will use default")
        return None

    score_str = form_data["score"]
    logger.debug("Raw score input: %s", sanitize_log_data(score_str))
    try:
        min_score = 0.0
        max_score = 2.0
        if score_str.isdigit():
            return int(score_str)
        elif float(score_str) < min_score:
            return 0
        elif float(score_str) > max_score:
            abort(
                HTTPStatus.BAD_REQUEST,
                f"Reported `score` <{score_str}> is too large. Should be "
                f"integer or float between {min_score} and {max_score}.",
            )
        else:
            return round(float(score_str) * task_score)
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST, f"Cannot parse `score` <{score_str}> to a number")


@bp.post("/report")
@requires_token
@requires_ready
def report_score(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    if course.status == CourseStatus.FINISHED:
        abort(HTTPStatus.CONFLICT, f"Cannot update score the course '{course_name}' is already finished.")

    rms_user, course, task, group = _validate_and_extract_params(
        request.form, app.rms_api, app.storage_api, course.course_name
    )

    reported_score = _process_score(request.form, task.score)
    if reported_score is None:
        reported_score = task.score
        logger.info("Got score=None; set max score for %s of %s", task.name, task.score)

    check_deadline = True
    if "check_deadline" in request.form:
        check_deadline = request.form["check_deadline"] is True or request.form["check_deadline"] == "True"

    allow_reduction = False
    if "allow_reduction" in request.form:
        allow_reduction = request.form["allow_reduction"] is True or request.form["allow_reduction"] == "True"

    submit_time_str = request.form.get("submit_time")
    submit_time = _process_submit_time(submit_time_str, app.storage_api.get_now_with_timezone(course.course_name))

    # Log with sanitized values
    logger.info("Use submit_time: %s", submit_time)
    logger.info(
        f"user={rms_user.username} (id={rms_user.id}), task={task.name}, "
        f"reported_score={reported_score}, submit_time={submit_time}, check_deadline={check_deadline}"
    )

    update_function = functools.partial(
        _update_score,
        course,
        group,
        task,
        reported_score,
        submit_time=submit_time,
        check_deadline=check_deadline,
        allow_reduction=allow_reduction,
    )
    final_score = app.storage_api.store_score(course.course_name, rms_user.id, task.name, update_function)

    logger.info("Stored final_score=%s for user=%s, task=%s", final_score, rms_user.username, task.name)

    # Recalculate and save student's final grade after score update
    try:
        # Get all student scores to recalculate grade
        student_scores = app.storage_api.get_scores(course.course_name, rms_user.id)
        bonus_score = app.storage_api.get_bonus_score(course.course_name, rms_user.id)
        max_score = app.storage_api.max_score_started(course.course_name)

        total_score = sum(student_scores.values()) + bonus_score
        percent = total_score * 100 / max_score if max_score > 0 else 0

        # Count large tasks solved
        large_count = 0
        for group_config in app.storage_api.get_groups(course.course_name, enabled=True, started=True):
            for task_config in group_config.tasks:
                if task_config.is_large and task_config.enabled:
                    task_score = student_scores.get(task_config.name, 0)
                    if task_score >= task_config.min_score:
                        large_count += 1

        student_data = {
            "username": rms_user.username,
            "scores": student_scores,
            "total_score": total_score,
            "percent": percent,
            "large_count": large_count,
        }

        app.storage_api.calculate_and_save_grade(course.course_name, rms_user.id, student_data)
        logger.info("Recalculated and saved grade for user=%s after score update", rms_user.username)
    except Exception as e:
        logger.error("Failed to recalculate grade for user=%s: %s", rms_user.username, str(e))
        # Don't fail the request if grade calculation fails

    return {
        "user_id": rms_user.id,
        "username": rms_user.username,
        "task": task.name,
        "score": final_score,
        "commit_time": submit_time.isoformat(sep=" ") if submit_time else "None",
        "submit_time": submit_time.isoformat(sep=" "),
    }, HTTPStatus.OK


@bp.get("/score")
@requires_token
@requires_ready
def get_score(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    rms_user, _, task, group = _validate_and_extract_params(
        request.form, app.rms_api, app.storage_api, course.course_name
    )

    student_scores = app.storage_api.get_scores(course.course_name, rms_user.id)

    try:
        student_task_score = student_scores[task.name]
        logger.info("user=%s, task=%s, score=%s", rms_user.username, task.name, student_task_score)
    except Exception:
        return f"Cannot get score for task {task.name} for {rms_user.username}", HTTPStatus.NOT_FOUND

    return {
        "user_id": rms_user.id,
        "username": rms_user.username,
        "task": task.name,
        "score": student_task_score,
    }, HTTPStatus.OK


@bp.post("/update_config")
@requires_token
def update_config(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    if course.status == CourseStatus.FINISHED:
        abort(HTTPStatus.CONFLICT, f"Cannot update config for the course '{course_name}' that is already finished.")

    logger.info("Running update_config for course=%s", course_name)

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)

        # Store the new config
        app.store_config(course_name, config_data)
        logger.info("Stored new config for course=%s", course_name)
    except Exception:
        logger.exception("Error while updating config for course=%s", course_name, exc_info=True)
        return f"Invalid config for course={course_name}", HTTPStatus.BAD_REQUEST

    # Recalculate grades for all students using the new config
    try:
        app.storage_api.recalculate_all_grades(course_name)
    except Exception:
        logger.exception("Failed to recalculate grades after config update for course=%s", course_name)

    return "", HTTPStatus.OK


@bp.post("/update_cache")
@requires_token
def update_cache(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    logger.info("Updating cached scores for course=%s", course_name)

    # ----- logic ----- #
    app.storage_api.update_cached_scores(course_name)

    logger.info("Cache updated for course=%s", course_name)
    return "", HTTPStatus.OK


@bp.get("/database")
@requires_auth_or_token
@requires_ready
def get_database(course_name: str, auth_method: AuthMethod) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    storage_api = app.storage_api
    course = __get_course_or_not_found(storage_api, course_name)

    if auth_method == AuthMethod.SESSION:
        rms_id = session["rms"]["rms_id"]
        is_course_admin = storage_api.check_if_course_admin(course.course_name, rms_id)
    else:
        is_course_admin = True

    logger.info("Fetching database snapshot for course=%s", course_name)
    table_data = get_database_table_data(app, course, include_admin_data=is_course_admin)
    return jsonify(table_data)


@bp.post("/database/update")
@requires_auth_or_token
@requires_ready
def update_database(course_name: str, auth_method: AuthMethod) -> ResponseReturnValue:
    """
    Update student scores in the database via API endpoint and recalculate grade.
    """
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    storage_api = app.storage_api

    if auth_method == AuthMethod.SESSION:
        rms_id = session["rms"]["rms_id"]
        username = session["rms"]["username"]
        logger.info("Request by admin=%s for course=%s", username, course_name)
        student_course_admin = storage_api.check_if_course_admin(course_name, rms_id)

        if not student_course_admin:
            return jsonify({"success": False, "message": "Only course admins can update scores"}), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    try:
        payload = ManytaskUpdateDatabasePayload.model_validate(request.get_json())
    except ValidationError as exc:
        logger.warning("Invalid request payload: %s", exc.errors())
        return jsonify(
            {"success": False, "message": "Invalid request data", "errors": exc.errors()}
        ), HTTPStatus.BAD_REQUEST

    new_scores = payload.new_scores
    row_data = payload.row_data

    student_username = row_data.username
    stored_user = storage_api.get_stored_user_by_username(student_username)
    student_rms_id = stored_user.rms_id
    total_score = row_data.total_score
    logger.info("Updating scores for user=%s: %s", sanitize_log_data(student_username), new_scores)

    try:
        for task_name, new_score in new_scores.items():
            if isinstance(new_score, (int, float)):
                new_score = storage_api.store_score(
                    course.course_name,
                    rms_id=student_rms_id,
                    task_name=task_name,
                    update_fn=lambda _flags, _old_score: int(new_score),
                )
                total_score += new_score - row_data.scores.get(task_name, 0)
                row_data.scores[task_name] = new_score
    except Exception as e:
        logger.error("Error updating database: %s", str(e))
        return jsonify(
            {"success": False, "message": "Internal error when trying to store score"}
        ), HTTPStatus.INTERNAL_SERVER_ERROR

    try:
        row_data.total_score = total_score
        max_score = app.storage_api.max_score_started(course.course_name)
        row_data.percent = total_score * 100 / max_score if max_score > 0 else 0

        # Calculate and save grade (applies DORESHKA logic if needed)
        # This updates final_grade but does NOT touch final_grade_override
        storage_api.calculate_and_save_grade(course.course_name, student_rms_id, row_data.model_dump())

        # Get effective grade (override if exists, otherwise final_grade)
        effective_grade = storage_api.get_effective_grade(course.course_name, student_rms_id)
        row_data.grade = effective_grade

        # Add override indicator for frontend
        row_data.grade_is_override = storage_api.is_grade_overridden(course.course_name, student_rms_id)

        logger.info("Successfully updated scores for user=%s", sanitize_log_data(student_username))
        return jsonify(
            {
                "success": True,
                "row_data": row_data.model_dump_json(),
            }
        ), HTTPStatus.OK

    except Exception as e:
        logger.error("Error calculating grade: %s", str(e))
        return jsonify(
            {"success": False, "message": "Internal error when calculating new grade. Try refresh page."}
        ), HTTPStatus.INTERNAL_SERVER_ERROR


@bp.post("/comment/update")
@requires_auth
@requires_ready
def update_comment(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    storage_api = app.storage_api

    admin_rms_id = session["rms"]["rms_id"]
    profile_username_ = session["rms"]["username"]
    logger.info("Comment update request by user=%s for course=%s", profile_username_, course_name)

    student_course_admin = storage_api.check_if_course_admin(course.course_name, admin_rms_id)

    if not student_course_admin:
        return jsonify({"success": False, "message": "Only course admins can update comments"}), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    try:
        data = request.get_json()
        username = data.get("username")

        if not username:
            return jsonify({"success": False, "message": "Username is required"}), HTTPStatus.BAD_REQUEST

        stored_user = storage_api.get_stored_user_by_username(username)
        student_rms_id = stored_user.rms_id

        raw_comment = data.get("comment")
        sanitized_comment, error = sanitize_and_validate_comment(raw_comment)

        if error:
            return jsonify({"success": False, "message": error}), HTTPStatus.BAD_REQUEST

        storage_api.update_student_comment(course.course_name, student_rms_id, sanitized_comment)

        logger.info("Successfully updated comment for user=%s", sanitize_log_data(username))
        return jsonify({"success": True}), HTTPStatus.OK

    except Exception as e:
        logger.error("Error updating comment: %s", str(e))
        return jsonify(
            {"success": False, "message": "Internal error when updating comment"}
        ), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.post("/namespaces")
@requires_auth
def create_namespace() -> ResponseReturnValue:
    """Create a new namespace.

    Only Instance Admin can create namespaces.
    Creates a GitLab group and DB record, assigns creator as namespace_admin.

    Request JSON structure::

        {
            "name": "HSE",
            "slug": "hse-namespace",
            "description": "Namespace for Higher School of Economics courses"
        }

    :returns: JSON response with status code and data:
        - 201: Namespace created successfully with id, name, slug, gitlab_group_id
        - 400: Bad request (invalid JSON, missing fields, invalid slug)
        - 403: Forbidden (not Instance Admin)
        - 409: Conflict (slug already exists)
        - 500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api
    rms_api = app.rms_api

    rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]
    if not storage_api.check_if_instance_admin(rms_id):
        return jsonify(
            ErrorResponse(error="Only Instance Admin can create namespaces").model_dump()
        ), HTTPStatus.FORBIDDEN

    request_data, error = validate_json_request(CreateNamespaceRequest)
    if error:
        return error
    assert request_data is not None

    name = request_data.name
    slug = request_data.slug
    description = request_data.description

    gitlab_group_id = None

    try:
        logger.info("Creating GitLab group for namespace name=%s slug=%s", name, slug)
        gitlab_group_id = rms_api.create_namespace_group(name=name, path=slug, description=description)
        logger.info("GitLab group created with id=%s", gitlab_group_id)

        rms_api.add_user_to_namespace_group(gitlab_group_id, rms_id)
        logger.info("Added creator rms_id=%s to GitLab group id=%s as Maintainer", rms_id, gitlab_group_id)

        namespace = storage_api.create_namespace(
            name=name,
            slug=slug,
            description=description,
            gitlab_group_id=gitlab_group_id,
            created_by_rms_id=rms_id,
        )

        logger.info(
            "Namespace created successfully by user=%s: id=%s slug=%s gitlab_group_id=%s",
            username,
            namespace.id,
            slug,
            gitlab_group_id,
        )

        response = NamespaceResponse(
            id=namespace.id,
            name=namespace.name,
            slug=namespace.slug,
            description=namespace.description,
            gitlab_group_id=namespace.gitlab_group_id,
        )
        return jsonify(response.model_dump()), HTTPStatus.CREATED

    except RuntimeError as e:
        logger.error("Failed to create GitLab group: %s", str(e))
        return jsonify(ErrorResponse(error=str(e)).model_dump()), HTTPStatus.CONFLICT

    except IntegrityError as e:
        logger.error("Database integrity error when creating namespace: %s", str(e))

        if gitlab_group_id is not None:
            try:
                logger.warning("GitLab group id=%s was created but namespace creation failed", gitlab_group_id)
            except Exception as cleanup_error:
                logger.error("Failed to cleanup GitLab group: %s", str(cleanup_error))

        return jsonify(ErrorResponse(error="Namespace with this slug already exists").model_dump()), HTTPStatus.CONFLICT

    except Exception as e:
        logger.error("Unexpected error creating namespace: %s", str(e), exc_info=True)

        if gitlab_group_id is not None:
            logger.warning("GitLab group id=%s was created but namespace creation failed", gitlab_group_id)

        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.get("/namespaces")
@requires_auth
def get_namespaces() -> ResponseReturnValue:
    """Get list of namespaces based on user access rights.

    Instance Admin sees all namespaces.
    Regular users see only namespaces where they have a role.

    Returns:
        200: List of namespaces
        500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api

    rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]
    is_instance_admin = storage_api.check_if_instance_admin(rms_id)

    try:
        if is_instance_admin:
            logger.info("Fetching all namespaces for Instance Admin user=%s", username)
            namespaces = storage_api.get_all_namespaces()

            namespace_list = [
                NamespaceResponse(
                    id=ns.id,
                    name=ns.name,
                    slug=ns.slug,
                    description=ns.description,
                    gitlab_group_id=ns.gitlab_group_id,
                    gitlab_group_path=app.rms_api.get_group_path_by_id(ns.gitlab_group_id),
                )
                for ns in namespaces
            ]
        else:
            logger.info("Fetching namespaces with roles for user=%s", username)
            namespace_role_pairs = storage_api.get_user_namespaces(rms_id)

            namespace_list = [
                NamespaceWithRoleResponse(
                    id=ns.id,
                    name=ns.name,
                    slug=ns.slug,
                    description=ns.description,
                    gitlab_group_id=ns.gitlab_group_id,
                    gitlab_group_path=app.rms_api.get_group_path_by_id(ns.gitlab_group_id),
                    role=role,
                )
                for ns, role in namespace_role_pairs
            ]

        result = NamespaceListResponse(namespaces=namespace_list)
        logger.info("Returning %d namespaces for user=%s", len(namespace_list), username)
        return jsonify(result.model_dump()), HTTPStatus.OK

    except Exception as e:
        logger.error("Error fetching namespaces for user=%s: %s", username, str(e), exc_info=True)
        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.get("/namespaces/<int:namespace_id>")
@requires_auth
def get_namespace_by_id(namespace_id: int) -> ResponseReturnValue:
    """Get detailed information about a specific namespace.

    Instance Admin can access any namespace (without role field).
    Regular users can only access namespaces where they have a role (with role field).

    Args:
        namespace_id: ID of the namespace

    Returns:
        200: Namespace information with user's role
        403: Forbidden (no access or namespace doesn't exist)
        500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api

    rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]

    try:
        namespace, role = storage_api.get_namespace_by_id(namespace_id, rms_id)

        result: NamespaceResponse | NamespaceWithRoleResponse
        if role is not None:
            result = NamespaceWithRoleResponse(
                id=namespace.id,
                name=namespace.name,
                slug=namespace.slug,
                description=namespace.description,
                gitlab_group_id=namespace.gitlab_group_id,
                role=role,
            )
        else:
            result = NamespaceResponse(
                id=namespace.id,
                name=namespace.name,
                slug=namespace.slug,
                description=namespace.description,
                gitlab_group_id=namespace.gitlab_group_id,
            )

        logger.info("User %s accessed namespace id=%s", username, namespace_id)
        return jsonify(result.model_dump()), HTTPStatus.OK

    except PermissionError as e:
        logger.warning("Access denied for user=%s to namespace id=%s", username, namespace_id)
        return jsonify(ErrorResponse(error="Access denied").model_dump()), HTTPStatus.FORBIDDEN

    except Exception as e:
        logger.error("Error fetching namespace id=%s for user=%s: %s", namespace_id, username, str(e), exc_info=True)
        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.post("/namespaces/<int:namespace_id>/users")
@requires_auth
@requires_json_validation(AddUserToNamespaceRequest)
@requires_namespace_admin(return_404_if_not_found=True)
def add_user_to_namespace(
    namespace_id: int, namespace: Any, validated_data: AddUserToNamespaceRequest
) -> ResponseReturnValue:
    """Add a user to a namespace with a specific role.

    Only Instance Admin or Namespace Admin can add users.

    Request JSON:
    {
        "user_id": 45,
        "role": "namespace_admin" | "program_manager"
    }

    Args:
        namespace_id: ID of the namespace

    Returns:
        201: User added successfully
        400: Bad request (invalid JSON, missing fields, invalid role)
        403: Forbidden (not Instance Admin or Namespace Admin)
        404: Not found (user or namespace doesn't exist)
        409: Conflict (user already has a role in this namespace)
        500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api
    rms_api = app.rms_api

    rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]

    user_id = validated_data.user_id
    role = validated_data.role

    try:
        try:
            rms_user = rms_api.get_rms_user_by_id(str(user_id))
        except Exception as e:
            logger.error("User with id=%s not found in RMS: %s", user_id, str(e))
            return jsonify(ErrorResponse(error=f"User with id={user_id} not found").model_dump()), HTTPStatus.NOT_FOUND

        # Сначала проверяем, что пользователь существует в локальной БД
        # (пользователь должен был хотя бы раз залогиниться в manytask)
        try:
            user_on_namespace = storage_api.add_user_to_namespace(
                namespace_id=namespace_id,
                user_rms_id=str(user_id),
                role=role,
                assigned_by_rms_id=rms_id,
            )
        except NoResultFound as e:
            logger.warning("User id=%s not registered in manytask: %s", user_id, str(e))
            return jsonify(
                ErrorResponse(
                    error=f"User with id={user_id} is not registered in manytask. The user must log in at least once."
                ).model_dump()
            ), HTTPStatus.NOT_FOUND
        except IntegrityError:
            logger.warning("User id=%s already has a role in namespace id=%s", user_id, namespace_id)
            return jsonify(
                ErrorResponse(error="User already has a role in this namespace").model_dump()
            ), HTTPStatus.CONFLICT
        except ValueError as e:
            logger.error("Invalid role %s: %s", role, str(e))
            return jsonify(ErrorResponse(error=str(e)).model_dump()), HTTPStatus.BAD_REQUEST

        # Добавляем в GitLab группу только после успешного добавления в БД
        try:
            rms_api.add_user_to_namespace_group(gitlab_group_id=namespace.gitlab_group_id, user_rms_id=str(user_id))
            logger.info("Added user id=%s to GitLab group id=%s", user_id, namespace.gitlab_group_id)
        except Exception as e:
            # TODO: откатить добавление в локальную БД
            logger.error("Failed to add user id=%s to GitLab group: %s", user_id, str(e))
            return jsonify(
                ErrorResponse(error="Failed to add user to GitLab group").model_dump()
            ), HTTPStatus.INTERNAL_SERVER_ERROR

        logger.info(
            "User %s added user_id=%s to namespace id=%s with role %s",
            username,
            user_id,
            namespace_id,
            role,
        )

        response = UserOnNamespaceResponse(
            id=user_on_namespace.id,
            user_id=user_on_namespace.user_id,
            namespace_id=user_on_namespace.namespace_id,
            role=role,
        )
        return jsonify(response.model_dump()), HTTPStatus.CREATED

    except Exception as e:
        logger.error(
            "Unexpected error adding user_id=%s to namespace id=%s: %s",
            user_id,
            namespace_id,
            str(e),
            exc_info=True,
        )
        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.get("/namespaces/<int:namespace_id>/users")
@requires_auth
@requires_namespace_admin()
def get_namespace_users(namespace_id: int, namespace: Any) -> ResponseReturnValue:
    """Get list of users in a namespace with their roles.

    Only Instance Admin or Namespace Admin can view users.
    Program Manager gets 403 Forbidden.

    Args:
        namespace_id: ID of the namespace

    Returns:
        200: List of users with roles
        403: Forbidden (not Instance Admin or Namespace Admin, or no access to namespace)
        500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api

    rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]

    try:
        users_list = storage_api.get_namespace_users(namespace_id)

        users = [NamespaceUserItem(user_id=user_id, role=user_role) for user_id, user_role in users_list]

        result = NamespaceUsersListResponse(users=users)

        logger.info(
            "Returning %d users for namespace id=%s to user=%s (rms_id=%s)", len(users), namespace_id, username, rms_id
        )
        return jsonify(result.model_dump()), HTTPStatus.OK

    except Exception as e:
        logger.error(
            "Error fetching users for namespace id=%s by user=%s: %s", namespace_id, username, str(e), exc_info=True
        )
        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.delete("/namespaces/<int:namespace_id>/users/<int:user_id>")
@requires_auth
@requires_namespace_admin()
def remove_user_from_namespace(namespace_id: int, user_id: int, namespace: Any) -> ResponseReturnValue:
    """Remove a user from a namespace.

    Only Instance Admin or Namespace Admin can remove users.
    Removes the user from the namespace in the database and GitLab group.

    Args:
        namespace_id: ID of the namespace
        user_id: Database User.id (not rms_id)

    Returns:
        204: User removed successfully
        403: Forbidden (not Instance Admin or Namespace Admin, or no access to namespace)
        404: Not found (user is not in the namespace)
        500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api
    rms_api = app.rms_api

    admin_rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]

    try:
        try:
            role, removed_rms_id = storage_api.remove_user_from_namespace(namespace_id, user_id)
            logger.info(
                "User %s (rms_id=%s) removed user_id=%s (rms_id=%s, role=%s) from namespace id=%s in database",
                username,
                admin_rms_id,
                user_id,
                removed_rms_id,
                role,
                namespace_id,
            )
        except NoResultFound:
            logger.warning("User id=%s not found in namespace id=%s", user_id, namespace_id)
            return jsonify(ErrorResponse(error="User not found in namespace").model_dump()), HTTPStatus.NOT_FOUND

        try:
            rms_api.remove_user_from_namespace_group(
                gitlab_group_id=namespace.gitlab_group_id, user_rms_id=removed_rms_id
            )
            logger.info(
                "User %s removed user rms_id=%s from GitLab group id=%s",
                username,
                removed_rms_id,
                namespace.gitlab_group_id,
            )
        except Exception as e:
            logger.error(
                "Failed to remove user rms_id=%s from GitLab group id=%s: %s",
                removed_rms_id,
                namespace.gitlab_group_id,
                str(e),
            )

        logger.info(
            "User %s successfully removed user_id=%s from namespace id=%s",
            username,
            user_id,
            namespace_id,
        )
        return "", HTTPStatus.NO_CONTENT

    except Exception as e:
        logger.error(
            "Unexpected error removing user_id=%s from namespace id=%s by user=%s: %s",
            user_id,
            namespace_id,
            username,
            str(e),
            exc_info=True,
        )
        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.patch("/namespaces/<int:namespace_id>/users/<int:user_id>")
@requires_auth
@requires_json_validation(UpdateUserRoleRequest)
@requires_namespace_admin()
def update_user_role_in_namespace(
    namespace_id: int, user_id: int, namespace: Any, validated_data: UpdateUserRoleRequest
) -> ResponseReturnValue:
    """Update a user's role in a namespace.

    Only Instance Admin or Namespace Admin can update roles.
    Setting role to 'student' removes the user from the namespace and GitLab group.

    Request JSON:
    {
        "role": "namespace_admin" | "program_manager" | "student"
    }

    Args:
        namespace_id: ID of the namespace
        user_id: Database User.id (not rms_id)

    Returns:
        200: Role updated successfully
        400: Bad request (invalid role)
        403: Forbidden (not Instance Admin or Namespace Admin)
        404: Not found (user is not in the namespace)
        500: Internal server error (including GitLab errors)
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api
    rms_api = app.rms_api

    admin_rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]
    new_role = validated_data.role

    try:
        # First, get the user's rms_id before making any changes
        try:
            stored_user = storage_api.get_stored_user_by_db_id(user_id)
            if stored_user is None:
                return jsonify(ErrorResponse(error="User not found").model_dump()), HTTPStatus.NOT_FOUND
            rms_id = stored_user.rms_id
        except Exception as e:
            logger.error("Failed to get user info for user_id=%s: %s", user_id, str(e))
            return jsonify(ErrorResponse(error="User not found").model_dump()), HTTPStatus.NOT_FOUND

        # If demoting to student, we need to remove from GitLab first
        # If GitLab fails, we don't want to change the database
        if new_role == "student":
            try:
                rms_api.remove_user_from_namespace_group(gitlab_group_id=namespace.gitlab_group_id, user_rms_id=rms_id)
                logger.info(
                    "User %s removed user rms_id=%s from GitLab group id=%s (role change to student)",
                    username,
                    rms_id,
                    namespace.gitlab_group_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to remove user rms_id=%s from GitLab group id=%s: %s",
                    rms_id,
                    namespace.gitlab_group_id,
                    str(e),
                )
                return jsonify(
                    ErrorResponse(error=f"Failed to remove user from GitLab group: {str(e)}").model_dump()
                ), HTTPStatus.INTERNAL_SERVER_ERROR

        # Now update the database
        try:
            old_role, actual_new_role, _ = storage_api.update_user_role_in_namespace(namespace_id, user_id, new_role)
            logger.info(
                "User %s updated role for user_id=%s in namespace id=%s: %s -> %s",
                username,
                user_id,
                namespace_id,
                old_role,
                actual_new_role,
            )
        except NoResultFound:
            logger.warning("User id=%s not found in namespace id=%s", user_id, namespace_id)
            return jsonify(ErrorResponse(error="User not found in namespace").model_dump()), HTTPStatus.NOT_FOUND
        except ValueError as e:
            logger.warning("Invalid role %s: %s", new_role, str(e))
            return jsonify(ErrorResponse(error=str(e)).model_dump()), HTTPStatus.BAD_REQUEST

        return jsonify(
            {
                "success": True,
                "old_role": old_role,
                "new_role": actual_new_role,
                "user_id": user_id,
            }
        ), HTTPStatus.OK

    except Exception as e:
        logger.error(
            "Unexpected error updating role for user_id=%s in namespace id=%s by user=%s: %s",
            user_id,
            namespace_id,
            username,
            str(e),
            exc_info=True,
        )
        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@namespace_bp.post("/admin/courses")
@requires_auth
@requires_json_validation(CreateCourseRequest)
def create_course_api(validated_data: CreateCourseRequest) -> ResponseReturnValue:
    """Create a new course in a namespace with owners.

    Only Instance Admin or Namespace Admin can create courses.
    Creates GitLab course group, public repo, and students group.
    Assigns owners as course admins.

    Request JSON:
    {
        "namespace_id": 12,
        "course_name": "Algorithms 2024 Spring",
        "slug": "algorithms-2024-spring",
        "owners": [45, 46]  // Optional: list of user rms_ids
    }

    For courses without namespace, pass namespace_id = 0.

    Returns:
        201: Course created successfully
        400: Bad request (invalid data)
        403: Forbidden (no access to namespace or owners not valid)
        404: Not found (namespace doesn't exist)
        409: Conflict (course with this slug already exists)
        500: Internal server error
    """
    app: CustomFlask = current_app  # type: ignore
    storage_api = app.storage_api
    rms_api = app.rms_api

    rms_id = session["rms"]["rms_id"]
    username = session["auth"]["username"]
    namespace_id = validated_data.namespace_id
    course_name = validated_data.course_name
    course_slug = validated_data.slug
    owner_rms_ids = validated_data.owners or []

    logger.info(
        "User %s creating course course_name=%s slug=%s in namespace_id=%s with owners=%s",
        username,
        course_name,
        course_slug,
        namespace_id,
        owner_rms_ids,
    )

    course_group_id = None
    public_project_id = None
    students_group_id = None

    try:
        is_instance_admin = storage_api.check_if_instance_admin(rms_id)

        namespace = None
        role = None
        if namespace_id == 0:
            if not is_instance_admin:
                logger.warning("User %s attempted to create course without namespace", username)
                return jsonify(
                    ErrorResponse(error="Only Instance Admin can create courses without namespace").model_dump()
                ), HTTPStatus.FORBIDDEN
        else:
            try:
                namespace, role = storage_api.get_namespace_by_id(namespace_id, rms_id)
            except (PermissionError, NoResultFound):
                logger.warning(
                    "User %s attempted to create course in inaccessible namespace id=%s", username, namespace_id
                )
                return jsonify(
                    ErrorResponse(error="Namespace not found or access denied").model_dump()
                ), HTTPStatus.NOT_FOUND

            if not is_instance_admin and role != "namespace_admin":
                logger.warning(
                    "User %s with role %s attempted to create course in namespace id=%s",
                    username,
                    role,
                    namespace_id,
                )
                return jsonify(
                    ErrorResponse(error="Only Instance Admin or Namespace Admin can create courses").model_dump()
                ), HTTPStatus.FORBIDDEN

        if namespace_id == 0 and owner_rms_ids:
            return jsonify(
                ErrorResponse(error="Owners are not supported for courses without namespace").model_dump()
            ), HTTPStatus.BAD_REQUEST

        if owner_rms_ids:
            try:
                for owner_rms_id in owner_rms_ids:
                    try:
                        user = storage_api.get_stored_user_by_rms_id(owner_rms_id)
                        if user is None:
                            raise ValueError(f"User with rms_id={owner_rms_id} not found")
                    except Exception:
                        logger.error("Owner validation failed for rms_id=%s", owner_rms_id)
                        return jsonify(
                            ErrorResponse(error=f"User with rms_id={owner_rms_id} not found").model_dump()
                        ), HTTPStatus.BAD_REQUEST

            except Exception as e:
                logger.error("Error validating owners: %s", str(e))
                return jsonify(ErrorResponse(error=f"Invalid owners: {str(e)}").model_dump()), HTTPStatus.BAD_REQUEST

        namespace_slug = namespace.slug if namespace is not None else ""
        gitlab_course_group = f"{namespace_slug}/{course_slug}" if namespace_slug else course_slug

        from datetime import datetime as dt

        now = dt.now()
        year = now.year
        semester = "spring" if 1 <= now.month <= 6 else "fall"

        gitlab_course_public_repo = f"{gitlab_course_group}/public-{year}-{semester}"
        gitlab_course_students_group = f"{gitlab_course_group}/students-{year}-{semester}"
        gitlab_default_branch = "main"

        try:
            logger.info(
                "Creating GitLab course group under namespace group_id=%s",
                namespace.gitlab_group_id if namespace else None,
            )
            course_group_id = rms_api.create_course_group(
                parent_group_id=namespace.gitlab_group_id if namespace else None,
                course_name=course_name,
                course_slug=course_slug,
            )
            logger.info("Created course group with id=%s", course_group_id)
        except RuntimeError as e:
            logger.error("Failed to create course group: %s", str(e))
            if "already exists" in str(e).lower():
                return jsonify(
                    ErrorResponse(error=f"Course with slug '{course_slug}' already exists").model_dump()
                ), HTTPStatus.CONFLICT
            return jsonify(
                ErrorResponse(error=f"Failed to create course group: {str(e)}").model_dump()
            ), HTTPStatus.INTERNAL_SERVER_ERROR

        try:
            logger.info("Creating public repo %s", gitlab_course_public_repo)
            rms_api.create_public_repo(gitlab_course_group, gitlab_course_public_repo)
            public_project_id = 1  # Placeholder
            logger.info("Created public repo")
        except Exception as e:
            logger.error("Failed to create public repo: %s", str(e))
            if course_group_id:
                rms_api.delete_group(course_group_id)
            return jsonify(
                ErrorResponse(error=f"Failed to create public repo: {str(e)}").model_dump()
            ), HTTPStatus.INTERNAL_SERVER_ERROR

        try:
            logger.info("Creating students group %s", gitlab_course_students_group)
            rms_api.create_students_group(gitlab_course_students_group)
            students_group_id = 1  # Placeholder
            logger.info("Created students group")
        except Exception as e:
            logger.error("Failed to create students group: %s", str(e))
            if public_project_id:
                rms_api.delete_project(public_project_id)
            if course_group_id:
                rms_api.delete_group(course_group_id)
            return jsonify(
                ErrorResponse(error=f"Failed to create students group: {str(e)}").model_dump()
            ), HTTPStatus.INTERNAL_SERVER_ERROR

        try:
            from .course import CourseConfig, CourseStatus, ManytaskDeadlinesType
            from .utils.generic import generate_token_hex

            course_config = CourseConfig(
                course_name=course_name,
                namespace_id=None if namespace_id == 0 else namespace_id,
                gitlab_course_group=gitlab_course_group,
                gitlab_course_public_repo=gitlab_course_public_repo,
                gitlab_course_students_group=gitlab_course_students_group,
                gitlab_default_branch=gitlab_default_branch,
                registration_secret=generate_token_hex(16),
                token=generate_token_hex(24),
                show_allscores=True,
                status=CourseStatus.CREATED,
                task_url_template="",
                links={},
                deadlines_type=ManytaskDeadlinesType.HARD,
            )

            success = storage_api.create_course(course_config)

            if not success:
                logger.error("Course with name=%s already exists in database", course_name)
                if students_group_id:
                    rms_api.delete_group(students_group_id)
                if public_project_id:
                    rms_api.delete_project(public_project_id)
                if course_group_id:
                    rms_api.delete_group(course_group_id)
                return jsonify(
                    ErrorResponse(error=f"Course with name '{course_name}' already exists").model_dump()
                ), HTTPStatus.CONFLICT

            logger.info("Created course in database: %s", course_name)

        except Exception as e:
            logger.error("Failed to create course in database: %s", str(e), exc_info=True)
            if students_group_id:
                rms_api.delete_group(students_group_id)
            if public_project_id:
                rms_api.delete_project(public_project_id)
            if course_group_id:
                rms_api.delete_group(course_group_id)
            return jsonify(
                ErrorResponse(error=f"Failed to create course in database: {str(e)}").model_dump()
            ), HTTPStatus.INTERNAL_SERVER_ERROR

        added_owners = []
        if owner_rms_ids:
            try:
                course_id = storage_api.get_course_id_by_name(course_name)
                if course_id is None:
                    raise RuntimeError(f"Course {course_name} not found after creation")

                added_owners = storage_api.add_course_owners(
                    course_id=course_id,
                    owner_rms_ids=owner_rms_ids,
                    namespace_id=namespace_id,
                )
                logger.info("Added %d owners to course %s", len(added_owners), course_name)

            except ValueError as e:
                logger.error("Failed to add owners: %s", str(e))
                return jsonify(
                    ErrorResponse(error=f"Failed to add owners: {str(e)}").model_dump()
                ), HTTPStatus.BAD_REQUEST
            except Exception as e:
                logger.error("Failed to add owners: %s", str(e), exc_info=True)
                return jsonify(
                    ErrorResponse(error=f"Failed to add owners: {str(e)}").model_dump()
                ), HTTPStatus.INTERNAL_SERVER_ERROR

        logger.info(
            "Successfully created course %s (slug=%s) in namespace %s with %d owners",
            course_name,
            course_slug,
            namespace.name if namespace else "(no namespace)",
            len(added_owners),
        )

        response_course_id = storage_api.get_course_id_by_name(course_name)
        if response_course_id is None:
            raise RuntimeError(f"Course {course_name} not found after creation")

        response = CourseResponse(
            id=response_course_id,
            course_name=course_name,
            slug=course_slug,
            namespace_id=namespace_id,
            gitlab_course_group=gitlab_course_group,
            gitlab_course_public_repo=gitlab_course_public_repo,
            gitlab_course_students_group=gitlab_course_students_group,
            status=CourseStatus.CREATED.value,
            owners=added_owners,
        )

        return jsonify(response.model_dump()), HTTPStatus.CREATED

    except Exception as e:
        logger.error(
            "Unexpected error creating course by user=%s: %s",
            username,
            str(e),
            exc_info=True,
        )
        try:
            if students_group_id:
                rms_api.delete_group(students_group_id)
            if public_project_id:
                rms_api.delete_project(public_project_id)
            if course_group_id:
                rms_api.delete_group(course_group_id)
        except Exception as rollback_error:
            logger.error("Error during rollback: %s", str(rollback_error))

        return jsonify(ErrorResponse(error="Internal server error").model_dump()), HTTPStatus.INTERNAL_SERVER_ERROR


@bp.post("/grade/override")
@requires_auth
@requires_ready
def override_grade(course_name: str) -> ResponseReturnValue:
    """Set manual grade override for a student."""
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    storage_api = app.storage_api

    admin_rms_id = session["rms"]["rms_id"]
    profile_username = session["rms"]["username"]
    logger.info("Grade override request by admin=%s for course=%s", profile_username, course_name)

    student_course_admin = storage_api.check_if_course_admin(course.course_name, admin_rms_id)

    if not student_course_admin:
        return jsonify({"success": False, "message": "Only course admins can override grades"}), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    try:
        data = request.get_json()
        username = data.get("username")
        new_grade = data.get("grade")

        if not username:
            return jsonify({"success": False, "message": "Username is required"}), HTTPStatus.BAD_REQUEST

        if new_grade is None:
            return jsonify({"success": False, "message": "Grade is required"}), HTTPStatus.BAD_REQUEST

        try:
            new_grade = int(new_grade)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Grade must be an integer"}), HTTPStatus.BAD_REQUEST

        stored_user = storage_api.get_stored_user_by_username(username)
        student_rms_id = stored_user.rms_id
        storage_api.override_grade(course.course_name, student_rms_id, new_grade)

        logger.info("Successfully set grade override for user=%s to %d", sanitize_log_data(username), new_grade)
        return jsonify({"success": True}), HTTPStatus.OK

    except Exception as e:
        logger.error("Error overriding grade: %s", str(e))
        return jsonify(
            {"success": False, "message": "Internal error when overriding grade"}
        ), HTTPStatus.INTERNAL_SERVER_ERROR


@bp.post("/grade/clear_override")
@requires_auth
@requires_ready
def clear_grade_override(course_name: str) -> ResponseReturnValue:
    """Clear manual grade override for a student."""
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    storage_api = app.storage_api

    admin_rms_id = session["rms"]["rms_id"]
    profile_username = session["rms"]["username"]
    logger.info("Clear grade override request by admin=%s for course=%s", profile_username, course_name)

    student_course_admin = storage_api.check_if_course_admin(course.course_name, admin_rms_id)

    if not student_course_admin:
        return jsonify(
            {"success": False, "message": "Only course admins can clear grade overrides"}
        ), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    try:
        data = request.get_json()
        username = data.get("username")

        if not username:
            return jsonify({"success": False, "message": "Username is required"}), HTTPStatus.BAD_REQUEST

        stored_user = storage_api.get_stored_user_by_username(username)
        student_rms_id = stored_user.rms_id
        storage_api.clear_grade_override(course.course_name, student_rms_id)

        logger.info("Successfully cleared grade override for user=%s", sanitize_log_data(username))
        return jsonify({"success": True}), HTTPStatus.OK

    except Exception as e:
        logger.error("Error clearing grade override: %s", str(e))
        return jsonify(
            {"success": False, "message": "Internal error when clearing grade override"}
        ), HTTPStatus.INTERNAL_SERVER_ERROR
