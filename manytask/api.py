from __future__ import annotations

import functools
import logging
import secrets
import tempfile
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

import yaml
from flask import Blueprint, Response, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from manytask.database import TaskDisabledError

from .auth import requires_auth
from .config import ManytaskGroupConfig, ManytaskTaskConfig
from .course import DEFAULT_TIMEZONE, Course, get_current_time
from .database_utils import get_database_table_data
from .glab import Student
from .main import CustomFlask
from .utils import get_current_course_from_cookies, get_current_course_from_headers

logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")


def requires_tokens(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        token = request.form.get("token", request.headers.get("Authorization", ""))
        if not token:
            abort(HTTPStatus.FORBIDDEN)

        course = get_current_course_from_headers(request.headers)

        token = token.split()[-1]

        if not secrets.compare_digest(token, course.token):
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

    if not check_deadline:
        return int(score)

    extra_time = _parse_flags(flags)

    multiplier = group.get_current_percent_multiplier(now=submit_time - extra_time)
    new_score = int(score * multiplier)

    return max(old_score, new_score)

    # if check_deadline and task.is_overdue_second(extra_time, submit_time=submit_time):
    #     return old_score
    # if check_deadline and task.is_overdue(extra_time, submit_time=submit_time):
    #     return int(second_deadline_max * score)
    # return int(score)


@bp.get("/healthcheck")
def healthcheck() -> ResponseReturnValue:
    return "OK", HTTPStatus.OK


def _validate_and_extract_params(form_data: dict[str, Any]) -> tuple[str, int | None, str | None, bool, str | None]:
    """Validate and extract parameters from form data."""
    if "task" not in form_data:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required attribute `task`")
    task_name = form_data["task"]

    if "user_id" not in form_data and "username" not in form_data:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required attribute `user_id` or `username`")

    user_id = int(form_data["user_id"]) if "user_id" in form_data else None
    username = form_data["username"] if "username" in form_data else None

    check_deadline = True
    if "check_deadline" in form_data:
        check_deadline = form_data["check_deadline"] is True or form_data["check_deadline"] == "True"

    submit_time_str = form_data.get("submit_time")

    return task_name, user_id, username, check_deadline, submit_time_str


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


def _get_student(
    gitlab_api: Any, user_id: int | None, username: str | None, course_group: str, course_students_group: str
) -> Student:
def _get_student(
    gitlab_api: Any, user_id: int | None, username: str | None, course_group: str, course_students_group: str
) -> Student:
    """Get student by user_id or username."""
    try:
        if username:
            return gitlab_api.get_student_by_username(username, course_group, course_students_group)
        elif user_id:
            return gitlab_api.get_student(user_id, course_group, course_students_group)
        else:
            assert False, "unreachable"
    except Exception:
        abort(HTTPStatus.NOT_FOUND, f"There is no student with user_id {user_id} or username {username}")


def _handle_files(files: dict[str, FileStorage], task_name: str, username: str, solutions_api: Any) -> None:
    """Handle file uploads for the task."""
    with tempfile.TemporaryDirectory() as temp_folder_str:
        temp_folder_path = Path(temp_folder_str)
        for file in files.values():
            assert file is not None and file.filename is not None
            secured_filename = secure_filename(file.filename)
            file.save(temp_folder_path / secured_filename)
        solutions_api.store_task_from_folder(task_name, username, temp_folder_path)


@bp.post("/report")
@requires_tokens
def report_score() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = get_current_course_from_headers(request.headers)

    task_name, user_id, username, check_deadline, submit_time_str = _validate_and_extract_params(request.form)

    try:
        group, task = app.storage_api.find_task(course.course_name, task_name)
    except (KeyError, TaskDisabledError):
        return (
            f"There is no task with name `{task_name}` (or it is closed for submission)",
            HTTPStatus.NOT_FOUND,
        )

    reported_score = _process_score(request.form, task.score)
    if reported_score is None:
        reported_score = task.score
        logger.info(f"Got score=None; set max score for {task.name} of {task.score}")

    student = _get_student(
        app.gitlab_api, user_id, username, course.gitlab_course_group, course.gitlab_course_students_group
    )

    submit_time = _process_submit_time(submit_time_str, app.storage_api.get_now_with_timezone(course.course_name))

    # Log with sanitized values
    logger.info(f"Save score {reported_score} for @{student} on task {task.name} check_deadline {check_deadline}")
    logger.info(f"verify deadline: Use submit_time={submit_time}")

    update_function = functools.partial(
        _update_score,
        group,
        task,
        reported_score,
        submit_time=submit_time,
        check_deadline=check_deadline,
    )
    final_score = app.storage_api.store_score(course.course_name, student, task.name, update_function)

    files = request.files.to_dict()
    if files:
        _handle_files(files, task_name, student.username, app.solutions_api)

    return {
        "user_id": student.id,
        "username": student.username,
        "task": task.name,
        "score": final_score,
        "commit_time": submit_time.isoformat(sep=" ") if submit_time else "None",
        "submit_time": submit_time.isoformat(sep=" "),
    }, HTTPStatus.OK


@bp.get("/score")
@requires_tokens
def get_score() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = get_current_course_from_cookies(request.cookies)

    # ----- get and validate request parameters ----- #
    if "task" not in request.form:
        return "You didn't provide required attribute `task`", HTTPStatus.BAD_REQUEST
    task_name = request.form["task"]

    if "user_id" not in request.form and "username" not in request.form:
        return "You didn't provide required attribute `user_id` or `username`", HTTPStatus.BAD_REQUEST
    user_id = None
    username = None
    if "user_id" in request.form:
        user_id = int(request.form["user_id"])
    if "username" in request.form:
        username = request.form["username"]

    # ----- logic ----- #
    try:
        group, task = app.storage_api.find_task(course.course_name, task_name)
    except (KeyError, TaskDisabledError):
        return (
            f"There is no task with name `{task_name}` (or it is closed for submission)",
            HTTPStatus.NOT_FOUND,
        )

    try:
        if username:
            student = app.gitlab_api.get_student_by_username(
                username, course.gitlab_course_group, course.gitlab_course_students_group
            )
        elif user_id:
            student = app.gitlab_api.get_student(
                user_id, course.gitlab_course_group, course.gitlab_course_students_group
            )
        else:
            assert False, "unreachable"
        student_scores = app.storage_api.get_scores(course.course_name, student.username)
    except Exception:
        return f"There is no student with user_id {user_id} or username {username}", HTTPStatus.NOT_FOUND

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
@requires_tokens
def update_config() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    logger.info("Running update_config")

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)

        # Store the new config
        app.store_config(config_data)
    except Exception as e:
        logger.exception(e)
        return f"Invalid config\n {e}", HTTPStatus.BAD_REQUEST

    return "", HTTPStatus.OK


@bp.post("/update_cache")
@requires_tokens
def update_cache() -> ResponseReturnValue:  # TODO: remove this
    app: CustomFlask = current_app  # type: ignore

    logger.info("Running update_cache")

    # ----- logic ----- #
    app.storage_api.update_cached_scores()

    return "", HTTPStatus.OK


@bp.get("/solutions")
@requires_tokens
def get_solutions() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = get_current_course_from_headers(request.headers)

    # ----- get and validate request parameters ----- #
    if "task" not in request.form:
        return "You didn't provide required attribute `task`", HTTPStatus.BAD_REQUEST
    task_name = request.form["task"]

    # TODO: parameter to return not aggregated solutions

    # ----- logic ----- #
    try:
        _, _ = app.storage_api.find_task(course.course_name, task_name)
    except (KeyError, TaskDisabledError):
        return f"There is no task with name `{task_name}` (or it is disabled)", HTTPStatus.NOT_FOUND

    zip_bytes_io = app.solutions_api.get_task_aggregated_zip_io(task_name)
    if not zip_bytes_io:
        return f"Unable to get zip for {task_name}", 500

    _now_str = datetime.now(UTC).strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"aggregated-solutions-{task_name}-{_now_str}.zip"

    return Response(
        zip_bytes_io.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )


@bp.get("/database")
@requires_auth
def get_database() -> ResponseReturnValue:
    course: Course = get_current_course_from_cookies(request.cookies)

    table_data = get_database_table_data(course)
    return jsonify(table_data)


@bp.post("/database/update")
@requires_auth
def update_database() -> ResponseReturnValue:
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
    course: Course = get_current_course_from_cookies(request.cookies)
    storage_api = app.storage_api

    student = app.gitlab_api.get_student(
        session["gitlab"]["user_id"], course.gitlab_course_group, course.gitlab_course_students_group
    )
    stored_user = storage_api.get_stored_user(course.course_name, student)
    student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

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
        student = Student(
            id=0,
            username=username,
            name=username,
            repo=app.gitlab_api.get_url_for_repo(
                username=username, course_students_group=course.gitlab_course_students_group
            ),
        )
        for task_name, new_score in new_scores.items():
            if isinstance(new_score, (int, float)):
                storage_api.store_score(
                    course_name=course.course_name,
                    student=student,
                    task_name=task_name,
                    update_fn=lambda _flags, _old_score: int(new_score),
                )
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return jsonify({"success": False, "message": "Internal error when trying to store score"}), 500
