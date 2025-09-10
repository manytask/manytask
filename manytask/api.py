from __future__ import annotations

import functools
import logging
from enum import Enum
import secrets
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Callable

import yaml
from flask import Blueprint, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue

from manytask.abstract import StorageApi
from manytask.database import TaskDisabledError
from manytask.glab import GitLabApiException

from .abstract import RmsApi, RmsUser
from .auth import requires_ready, check_authenticated
from .utils.generic import sanitize_log_data
from .config import ManytaskGroupConfig, ManytaskTaskConfig
from .course import DEFAULT_TIMEZONE, Course, get_current_time
from .main import CustomFlask
from .utils.database import get_database_table_data


logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api/<course_name>")


def get_course_or_not_found(app: CustomFlask, course_name: str) -> Course:
    course = app.storage_api.get_course(course_name)
    if course is None:
        logger.warning(f"Course not found: {course_name}")
        abort(HTTPStatus.NOT_FOUND, "Course not found")
    return course


def check_token(app: CustomFlask, course: Course) -> bool:
    course_name = course.course_name
    logger.debug(f"Checking token for course={course_name}")

    course_token = course.token
    token = request.form.get("token", request.headers.get("Authorization", ""))
    if not token or not course_token:
        logger.warning(f"Missing token for course={course_name}")
        return False
    token = token.split()[-1]
    if not secrets.compare_digest(token, course_token):
        logger.warning(f"Invalid token for course={course_name}")
        return False

    logger.debug(f"Token validated for course={course_name}")
    return True


def requires_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        course_name = kwargs["course_name"]
        course = get_course_or_not_found(app, course_name)
        if not check_token(app, course):
            abort(HTTPStatus.FORBIDDEN)

        return f(*args, **kwargs)

    return decorated


class AuthMethod(Enum):
    COURSE_TOKEN = "course_token"
    SESSION = "session"


def requires_auth_or_token[T](f: Callable[..., T]) -> Callable[..., T]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> T:
        app: CustomFlask = current_app  # type: ignore

        course_name = kwargs["course_name"]
        course = get_course_or_not_found(app, course_name)
        if check_authenticated(app):
            return f(*args, **kwargs, method=AuthMethod.SESSION)
        if check_token(app, course):
            return f(*args, **kwargs, method=AuthMethod.COURSE_TOKEN)

        abort(HTTPStatus.FORBIDDEN)

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
            logger.error(f"Could not parse date from flag {flags}")
        if parsed is not None and get_current_time() <= parsed:
            days = int(flags[left_colon + 1 : right_colon])
            extra_time = timedelta(days=days)
            logger.debug(f"Parsed extra_time={extra_time} from flags={flags}")
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
        logger.debug(f"Applied multiplier={multiplier}, adjusted_score={score}")

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
            logger.info(f"Found user by id={user_id}: {rms_user.username}")
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
        logger.warning(f"Task not found or disabled: {sanitize_log_data(task_name)}")
        abort(HTTPStatus.NOT_FOUND, f"There is no task with name `{task_name}` (or it is closed for submission)")

    return rms_user, course, task, group


def _process_submit_time(submit_time_str: str | None, now_with_timezone: datetime) -> datetime:
    """Process and validate submit time."""
    submit_time = None
    if submit_time_str:
        try:
            submit_time = datetime.strptime(submit_time_str, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            logger.warning(f"Invalid submit_time format: {sanitize_log_data(submit_time_str)}")
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
    logger.debug(f"Raw score input: {sanitize_log_data(score_str)}")
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
        logger.info(f"Got score=None; set max score for {task.name} of {task.score}")

    check_deadline = True
    if "check_deadline" in request.form:
        check_deadline = request.form["check_deadline"] is True or request.form["check_deadline"] == "True"

    submit_time_str = request.form.get("submit_time")
    submit_time = _process_submit_time(submit_time_str, app.storage_api.get_now_with_timezone(course.course_name))

    # Log with sanitized values
    logger.info(f"Use submit_time: {submit_time}")
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

    logger.info(f"Stored final_score={final_score} for user={rms_user.username}, task={task.name}")

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
        logger.info(f"user={rms_user.username}, task={task.name}, score={student_task_score}")
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

    logger.info(f"Running update_config for course={course_name}")

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)

        # Store the new config
        app.store_config(course_name, config_data)
        logger.info(f"Stored new config for course={course_name}")
    except Exception:
        logger.exception(f"Error while updating config for course={course_name}", exc_info=True)
        return f"Invalid config for course={course_name}", HTTPStatus.BAD_REQUEST

    return "", HTTPStatus.OK


@bp.post("/update_cache")
@requires_token
def update_cache(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    logger.info(f"Updating cached scores for course={course_name}")

    # ----- logic ----- #
    app.storage_api.update_cached_scores(course_name)

    logger.info(f"Cache updated for course={course_name}")
    return "", HTTPStatus.OK


@bp.get("/database")
@requires_auth_or_token
@requires_ready
def get_database(course_name: str, method: AuthMethod) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    storage_api = app.storage_api
    course = get_course_or_not_found(app, course_name)

    include_repo_urls = True

    if method == AuthMethod.SESSION:
        rms_user = app.rms_api.get_rms_user_by_id(session["gitlab"]["user_id"])
        include_repo_urls = storage_api.check_if_course_admin(course.course_name, rms_user.username)

    logger.info(f"Fetching database snapshot for course={course_name}")
    table_data = get_database_table_data(app, course, include_repo_urls=include_repo_urls)
    return jsonify(table_data)


@bp.post("/database/update")
@requires_auth_or_token
@requires_ready
def update_database(course_name: str, method: AuthMethod) -> ResponseReturnValue:
    """
    Update student scores in the database via API endpoint.

    This endpoint accepts POST requests with JSON data containing a username and scores to update.
    The request body should be in the format:
    {
        "username": str,
        "scores": {
            "task_name": score_value
        }
    }

    Returns:
        ResponseReturnValue: JSON response with success status and optional error message
    """
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    storage_api = app.storage_api

    if method == AuthMethod.SESSION:
        rms_user = app.rms_api.get_rms_user_by_id(session["gitlab"]["user_id"])
        logger.info(f"Request by admin={rms_user.username} for course={course_name}")

        student_course_admin = storage_api.check_if_course_admin(course.course_name, rms_user.username)

        if not student_course_admin:
            return jsonify({"success": False, "message": "Only course admins can update scores"}), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    data = request.get_json()
    if not data or "username" not in data or "scores" not in data:
        return jsonify({"success": False, "message": "Missing required fields"}), HTTPStatus.BAD_REQUEST

    username = data["username"]
    new_scores = data["scores"]
    logger.info(f"Updating scores for user={sanitize_log_data(username)}: {new_scores}")

    try:
        for task_name, new_score in new_scores.items():
            if isinstance(new_score, (int, float)):
                storage_api.store_score(
                    course.course_name,
                    username=username,
                    task_name=task_name,
                    update_fn=lambda _flags, _old_score: int(new_score),
                )
        logger.info(f"Successfully updated scores for user={sanitize_log_data(username)}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return jsonify({"success": False, "message": "Internal error when trying to store score"}), 500
