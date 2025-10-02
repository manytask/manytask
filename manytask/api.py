from __future__ import annotations

import functools
import logging
import secrets
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Callable

import yaml
from flask import Blueprint, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue
from enum import Enum
from pydantic import ValidationError

from manytask.abstract import StorageApi
from manytask.database import TaskDisabledError
from manytask.glab import GitLabApiException

from .abstract import RmsApi, RmsUser
from .auth import requires_auth, requires_ready
from .config import ManytaskGroupConfig, ManytaskTaskConfig, ManytaskUpdateDatabasePayload
from .course import DEFAULT_TIMEZONE, Course, get_current_time
from .main import CustomFlask
from .utils.database import get_database_table_data
from .utils.generic import sanitize_and_validate_comment, sanitize_log_data


logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api/<course_name>")


def __get_course_or_not_found(storage_api: StorageApi, course_name: str) -> Course:
    course = storage_api.get_course(course_name)
    if course is None:
        logger.warning("Course not found: %s", course_name)
        abort(HTTPStatus.NOT_FOUND, "Course not found")
    return course


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

    return max(old_score, score)


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
            user_id = int(form_data["user_id"])
            rms_user = rms_api.get_rms_user_by_id(user_id)
            logger.info("Found user by id=%s: %s", user_id, rms_user.username)
        except ValueError:
            abort(HTTPStatus.BAD_REQUEST, f"User ID is {form_data['user_id']}, but it must be an integer")
        except GitLabApiException:
            abort(HTTPStatus.NOT_FOUND, f"There is no student with user ID {user_id}")
    elif "username" in form_data:
        try:
            username = form_data["username"]
            rms_user = rms_api.get_rms_user_by_username(username)
        except GitLabApiException:
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
    )
    final_score = app.storage_api.store_score(course.course_name, rms_user.username, task.name, update_function)

    logger.info("Stored final_score=%s for user=%s, task=%s", final_score, rms_user.username, task.name)

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

    student_scores = app.storage_api.get_scores(course.course_name, rms_user.username)

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
        rms_user = app.rms_api.get_rms_user_by_id(session["gitlab"]["user_id"])
        is_course_admin = storage_api.check_if_course_admin(course.course_name, rms_user.username)
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
        username = session["profile"]["username"]
        logger.info("Request by admin=%s for course=%s", username, course_name)
        student_course_admin = storage_api.check_if_course_admin(course_name, username)

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

    username = row_data.username
    total_score = row_data.total_score
    logger.info("Updating scores for user=%s: %s", sanitize_log_data(username), new_scores)

    try:
        for task_name, new_score in new_scores.items():
            if isinstance(new_score, (int, float)):
                new_score = storage_api.store_score(
                    course.course_name,
                    username=username,
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
        new_grade = storage_api.get_grades(course.course_name).evaluate(row_data.model_dump())
        row_data.grade = 0 if new_grade is None else new_grade

        logger.info("Successfully updated scores for user=%s", sanitize_log_data(username))
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

    profile_username_ = session["profile"]["username"]
    logger.info("Comment update request by user=%s for course=%s", profile_username_, course_name)

    student_course_admin = storage_api.check_if_course_admin(course.course_name, profile_username_)

    if not student_course_admin:
        return jsonify({"success": False, "message": "Only course admins can update comments"}), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    try:
        data = request.get_json()
        username = data.get("username")

        if not username:
            return jsonify({"success": False, "message": "Username is required"}), HTTPStatus.BAD_REQUEST

        raw_comment = data.get("comment")
        sanitized_comment, error = sanitize_and_validate_comment(raw_comment)

        if error:
            return jsonify({"success": False, "message": error}), HTTPStatus.BAD_REQUEST

        storage_api.update_student_comment(course.course_name, username, sanitized_comment)

        logger.info("Successfully updated comment for user=%s", sanitize_log_data(username))
        return jsonify({"success": True}), HTTPStatus.OK

    except Exception as e:
        logger.error("Error updating comment: %s", str(e))
        return jsonify(
            {"success": False, "message": "Internal error when updating comment"}
        ), HTTPStatus.INTERNAL_SERVER_ERROR
