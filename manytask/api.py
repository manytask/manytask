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

from manytask.abstract import StorageApi
from manytask.database import TaskDisabledError
from manytask.glab import GitLabApi, GitLabApiException

from .auth import requires_auth, requires_ready
from .config import ManytaskGroupConfig, ManytaskTaskConfig
from .course import DEFAULT_TIMEZONE, Course, get_current_time
from .database_utils import get_database_table_data
from .glab import Student
from .main import CustomFlask

logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api/<course_name>")


def requires_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        course_name = kwargs["course_name"]
        course = app.storage_api.get_course(course_name)
        if course is None:
            abort(HTTPStatus.NOT_FOUND, "Course not found")

        course_token = course.token
        token = request.form.get("token", request.headers.get("Authorization", ""))
        if not token or not course_token:
            abort(HTTPStatus.FORBIDDEN)
        token = token.split()[-1]
        if not secrets.compare_digest(token, course_token):
            abort(HTTPStatus.FORBIDDEN)
        return f(*args, **kwargs)

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
    return extra_time


def _update_score(
    group: ManytaskGroupConfig,
    task: ManytaskTaskConfig,
    score: int,
    flags: str,
    old_score: int,
    submit_time: datetime,
    check_deadline: bool = True,
) -> int:
    if old_score < 0:
        return old_score

    if check_deadline:
        extra_time = _parse_flags(flags)

        multiplier = group.get_current_percent_multiplier(now=submit_time - extra_time)
        score = int(score * multiplier)

    return max(old_score, score)


@bp.get("/healthcheck")
@requires_ready
def healthcheck() -> ResponseReturnValue:
    return "OK", HTTPStatus.OK


def _validate_and_extract_params(
    form_data: dict[str, Any], gitlab_api: GitLabApi, storage_api: StorageApi, course_name: str
) -> tuple[Student, ManytaskTaskConfig, ManytaskGroupConfig]:
    """Validate and extract parameters from form data."""

    if "user_id" in form_data and "username" in form_data:
        abort(HTTPStatus.BAD_REQUEST, "Both `user_id` or `username` were provided, use only one")
    elif "user_id" in form_data:
        try:
            user_id = int(form_data["user_id"])
            student = gitlab_api.get_student(user_id)
        except ValueError:
            abort(HTTPStatus.BAD_REQUEST, f"User ID is {form_data['user_id']}, but it must be an integer")
        except GitLabApiException:
            abort(HTTPStatus.NOT_FOUND, f"There is no student with user ID {user_id}")
    elif "username" in form_data:
        try:
            username = form_data["username"]
            student = gitlab_api.get_student_by_username(username)
        except GitLabApiException:
            abort(HTTPStatus.NOT_FOUND, f"There is no student with username {username}")
    else:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required attribute `user_id` or `username`")

    if "task" not in form_data:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required attribute `task`")
    task_name = form_data["task"]

    try:
        group, task = storage_api.find_task(course_name, task_name)
    except (KeyError, TaskDisabledError):
        abort(HTTPStatus.NOT_FOUND, f"There is no task with name `{task_name}` (or it is closed for submission)")

    return student, task, group


def _process_submit_time(submit_time_str: str | None, now_with_timezone: datetime) -> datetime:
    """Process and validate submit time."""
    submit_time = None
    if submit_time_str:
        try:
            submit_time = datetime.strptime(submit_time_str, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            submit_time = None

    submit_time = submit_time or now_with_timezone
    submit_time.replace(tzinfo=now_with_timezone.tzinfo)
    return submit_time


def _process_score(form_data: dict[str, Any], task_score: int) -> int | None:
    """Process and validate score from form data."""
    if "score" not in form_data:
        return None

    score_str = form_data["score"]
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

    student, task, group = _validate_and_extract_params(
        request.form, app.gitlab_api, app.storage_api, course.course_name
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
        f"Will process score {reported_score} for @{student} on task {task.name} {'with' if check_deadline else 'without'} deadline check"
    )

    update_function = functools.partial(
        _update_score,
        group,
        task,
        reported_score,
        submit_time=submit_time,
        check_deadline=check_deadline,
    )
    final_score = app.storage_api.store_score(
        course.course_name,
        student.username,
        app.rms_api.get_url_for_repo(student.username, course.gitlab_course_students_group),
        task.name,
        update_function,
    )

    return {
        "user_id": student.id,
        "username": student.username,
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

    student, task, group = _validate_and_extract_params(
        request.form, app.gitlab_api, app.storage_api, course.course_name
    )

    student_scores = app.storage_api.get_scores(course.course_name, student.username)

    try:
        student_task_score = student_scores[task.name]
    except Exception:
        return f"Cannot get score for task {task.name} for {student.username}", HTTPStatus.NOT_FOUND

    return {
        "user_id": student.id,
        "username": student.username,
        "task": task.name,
        "score": student_task_score,
    }, HTTPStatus.OK


@bp.post("/update_config")
@requires_token
def update_config(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    logger.info("Running update_config")

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)

        # Store the new config
        app.store_config(course_name, config_data)
    except Exception as e:
        logger.exception(e)
        return f"Invalid config\n {e}", HTTPStatus.BAD_REQUEST

    return "", HTTPStatus.OK


@bp.post("/update_cache")
@requires_token
def update_cache(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    logger.info("Running update_cache")

    # ----- logic ----- #
    app.storage_api.update_cached_scores(course_name)

    return "", HTTPStatus.OK


@bp.get("/database")
@requires_auth
@requires_ready
def get_database(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    table_data = get_database_table_data(app, course_name)
    return jsonify(table_data)


@bp.post("/database/update")
@requires_auth
@requires_ready
def update_database(course_name: str) -> ResponseReturnValue:
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

    student = app.gitlab_api.get_student(session["gitlab"]["user_id"])
    stored_user = storage_api.get_stored_user(course.course_name, student.username)
    student_course_admin = stored_user.course_admin

    if not student_course_admin:
        return jsonify({"success": False, "message": "Only course admins can update scores"}), HTTPStatus.FORBIDDEN

    if not request.is_json:
        return jsonify({"success": False, "message": "Request must be JSON"}), HTTPStatus.BAD_REQUEST

    data = request.get_json()
    if not data or "username" not in data or "scores" not in data:
        return jsonify({"success": False, "message": "Missing required fields"}), HTTPStatus.BAD_REQUEST

    username = data["username"]
    new_scores = data["scores"]

    try:
        repo_name = app.rms_api.get_url_for_repo(
            username=username, course_students_group=course.gitlab_course_students_group
        )
        for task_name, new_score in new_scores.items():
            if isinstance(new_score, (int, float)):
                storage_api.store_score(
                    course.course_name,
                    username=username,
                    repo_name=repo_name,
                    task_name=task_name,
                    update_fn=lambda _flags, _old_score: int(new_score),
                )
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return jsonify({"success": False, "message": "Internal error when trying to store score"}), 500
