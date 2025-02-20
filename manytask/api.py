from __future__ import annotations

import functools
import logging
import os
import secrets
import tempfile
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml
from flask import Blueprint, Response, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from manytask.database import DataBaseApi

from .auth import requires_auth, requires_ready
from .config import ManytaskGroupConfig, ManytaskTaskConfig
from .course import DEFAULT_TIMEZONE, Course, get_current_time
from .database_utils import get_database_table_data
from .glab import Student

logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")


def requires_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        course: Course = current_app.course if hasattr(current_app, "course") else abort(HTTPStatus.FORBIDDEN)
        course_token: str = ""
        # TODO: unneed check when depricate googlesheet interface
        if isinstance(course.storage_api, DataBaseApi):
            db_course = course.storage_api.get_course(course.storage_api.course_name)
            if not db_course:
                abort(HTTPStatus.FORBIDDEN)
            course_token = db_course.token

        # TODO: delete when depricate googlesheet interface
        else:
            course_token = os.environ["MANYTASK_COURSE_TOKEN"]

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
@requires_ready
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


def _process_submit_time(submit_time_str: str | None, deadlines: Any) -> datetime:
    """Process and validate submit time."""
    submit_time = None
    if submit_time_str:
        try:
            submit_time = datetime.strptime(submit_time_str, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            submit_time = None

    submit_time = submit_time or deadlines.get_now_with_timezone()
    submit_time.replace(tzinfo=ZoneInfo(deadlines.timezone))
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


def _get_student(gitlab_api: Any, user_id: int | None, username: str | None) -> Student:
    """Get student by user_id or username."""
    try:
        if username:
            return gitlab_api.get_student_by_username(username)
        elif user_id:
            return gitlab_api.get_student(user_id)
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
@requires_token
@requires_ready
def report_score() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    task_name, user_id, username, check_deadline, submit_time_str = _validate_and_extract_params(request.form)

    try:
        group, task = course.deadlines.find_task(task_name)
    except KeyError:
        return (
            f"There is no task with name `{task_name}` (or it is closed for submission)",
            HTTPStatus.NOT_FOUND,
        )

    reported_score = _process_score(request.form, task.score)
    if reported_score is None:
        reported_score = task.score
        logger.info(f"Got score=None; set max score for {task.name} of {task.score}")

    student = _get_student(course.gitlab_api, user_id, username)

    submit_time = _process_submit_time(submit_time_str, course.deadlines)

    # fixme: sanitize input
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
    final_score = course.storage_api.store_score(student, task.name, update_function)

    files = request.files.to_dict()
    if files:
        _handle_files(files, task_name, student.username, course.solutions_api)

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
def get_score() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

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
        group, task = course.deadlines.find_task(task_name)
    except KeyError:
        return (
            f"There is no task with name `{task_name}` (or it is closed for submission)",
            HTTPStatus.NOT_FOUND,
        )

    try:
        if username:
            student = course.gitlab_api.get_student_by_username(username)
        elif user_id:
            student = course.gitlab_api.get_student(user_id)
        else:
            assert False, "unreachable"
        student_scores = course.storage_api.get_scores(student.username)
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
@requires_token
def update_config() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info("Running update_config")

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)

        # Update task groups (if necessary -- if there is an override) first
        course.storage_api.update_task_groups_from_config(config_data)

        # Store the new config
        course.store_config(config_data)
    except Exception as e:
        logger.exception(e)
        return f"Invalid config\n {e}", HTTPStatus.BAD_REQUEST

    # ----- logic ----- #
    # TODO: fix course config storing. may work one thread only =(
    # sync columns
    course.storage_api.sync_columns(course.deadlines)

    return "", HTTPStatus.OK


@bp.post("/update_cache")
@requires_token
def update_cache() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info("Running update_cache")

    # ----- logic ----- #
    course.storage_api.update_cached_scores()

    return "", HTTPStatus.OK


@bp.get("/solutions")
@requires_token
@requires_ready
def get_solutions() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if "task" not in request.form:
        return "You didn't provide required attribute `task`", HTTPStatus.BAD_REQUEST
    task_name = request.form["task"]

    # TODO: parameter to return not aggregated solutions

    # ----- logic ----- #
    try:
        _, _ = course.deadlines.find_task(task_name)
    except KeyError:
        return f"There is no task with name `{task_name}` (or it is disabled)", HTTPStatus.NOT_FOUND

    zip_bytes_io = course.solutions_api.get_task_aggregated_zip_io(task_name)
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
@requires_ready
def get_database() -> ResponseReturnValue:
    table_data = get_database_table_data()
    return jsonify(table_data)


@bp.post("/database/update")
@requires_auth
@requires_ready
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
    course: Course = current_app.course  # type: ignore
    storage_api = course.storage_api

    student = course.gitlab_api.get_student(session["gitlab"]["user_id"])
    stored_user = storage_api.get_stored_user(student)
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
        student = Student(id=0, username=username, name=username, repo=course.gitlab_api.get_url_for_repo(username))
        for task_name, new_score in new_scores.items():
            if isinstance(new_score, (int, float)):
                storage_api.store_score(
                    student=student, task_name=task_name, update_fn=lambda _flags, _old_score: int(new_score)
                )
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return jsonify({"success": False, "message": "Internal error when trying to store score"}), 500
