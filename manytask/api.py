from __future__ import annotations

import functools
import logging
import os
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml
from flask import Blueprint, Response, abort, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .auth import requires_auth, requires_ready
from .config import ManytaskGroupConfig, ManytaskTaskConfig
from .course import DEFAULT_TIMEZONE, Course, get_current_time
from .database_utils import get_database_table_data


logger = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")


def requires_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        tester_token = os.environ["TESTER_TOKEN"]
        token = request.form.get("token", request.headers.get("Authorization", ""))
        if not token:
            abort(403)
        token = token.split()[-1]
        if not secrets.compare_digest(token, tester_token):
            abort(403)

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
    return "OK", 200


@bp.post("/report")
@requires_token
@requires_ready
def report_score() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if "task" not in request.form:
        return "You didn't provide required attribute `task`", 400
    task_name = request.form["task"]

    if "user_id" not in request.form and "username" not in request.form:
        return "You didn't provide required attribute `user_id` or `username`", 400
    user_id = None
    username = None
    if "user_id" in request.form:
        user_id = int(request.form["user_id"])
    if "username" in request.form:
        username = request.form["username"]

    check_deadline = True
    if "check_deadline" in request.form:
        check_deadline = request.form["check_deadline"] is True or request.form["check_deadline"] == "True"

    submit_time = None
    submit_time_str = None
    if "submit_time" in request.form:
        submit_time_str = request.form["submit_time"]
    if submit_time_str:
        try:
            submit_time = datetime.strptime(submit_time_str, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            submit_time = None

    files: dict[str, FileStorage] = request.files.to_dict()  # may be empty

    # ----- logic ----- #
    try:
        group, task = course.deadlines.find_task(task_name)
    except KeyError:
        return (
            f"There is no task with name `{task_name}` (or it is closed for submission)",
            404,
        )

    reported_score: int | None = None
    if "score" in request.form:
        score_str = request.form["score"]
        try:
            if score_str.isdigit():
                reported_score = int(score_str)
            elif float(score_str) < 0.0:
                reported_score = 0
            elif float(score_str) > 2.0:
                return f"Reported `score` <{reported_score}> is too large. " + \
                        "Should be integer or float between 0.0 and 2.0.", 400
            else:
                reported_score = round(float(score_str) * task.score)
        except ValueError:
            return f"Cannot parse `score` <{reported_score}> to a number`", 400

    try:
        if username:
            student = course.gitlab_api.get_student_by_username(username)
        elif user_id:
            student = course.gitlab_api.get_student(user_id)
        else:
            assert False, "unreachable"
    except Exception:
        return f"There is no student with user_id {user_id} or username {username}", 404

    submit_time = submit_time or course.deadlines.get_now_with_timezone()
    submit_time.replace(tzinfo=ZoneInfo(course.deadlines.timezone))

    logger.info(f"Save score {reported_score} for @{student} on task {task.name} check_deadline {check_deadline}")
    logger.info(f"verify deadline: Use submit_time={submit_time}")

    if reported_score is None:
        reported_score = task.score
        logger.info(f"Got score=None; set max score for {task.name} of {task.score}")
    assert reported_score is not None

    update_function = functools.partial(
        _update_score,
        group,
        task,
        reported_score,
        submit_time=submit_time,
        check_deadline=check_deadline,
    )
    final_score = course.storage_api.store_score(student, task.name, update_function)

    # save pushed files if sent
    with tempfile.TemporaryDirectory() as temp_folder_str:
        temp_folder_path = Path(temp_folder_str)
        for file in files.values():
            assert file is not None and file.filename is not None
            secured_filename = secure_filename(file.filename)
            file.save(temp_folder_path / secured_filename)
        course.solutions_api.store_task_from_folder(task_name, student.username, temp_folder_path)

    return {
        "user_id": student.id,
        "username": student.username,
        "task": task.name,
        "score": final_score,
        "commit_time": submit_time.isoformat(sep=" ") if submit_time else "None",
        "submit_time": submit_time.isoformat(sep=" "),
    }, 200


@bp.get("/score")
@requires_token
@requires_ready
def get_score() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if "task" not in request.form:
        return "You didn't provide required attribute `task`", 400
    task_name = request.form["task"]

    if "user_id" not in request.form and "username" not in request.form:
        return "You didn't provide required attribute `user_id` or `username`", 400
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
            404,
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
        return f"There is no student with user_id {user_id} or username {username}", 404

    try:
        student_task_score = student_scores[task.name]
    except Exception:
        return f"Cannot get score for task {task.name} for {student.username}", 404

    return {
        "user_id": student.id,
        "username": student.username,
        "task": task.name,
        "score": student_task_score,
    }, 200


@bp.post("/update_config")
@requires_token
def update_config() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info("Running update_config")

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)
        course.store_config(config_data)
    except Exception as e:
        logger.exception(e)
        return f"Invalid config\n {e}", 400

    # ----- logic ----- #
    # TODO: fix course config storing. may work one thread only =(
    # sync columns
    course.storage_api.sync_columns(course.deadlines)

    return "", 200


@bp.post("/update_cache")
@requires_token
def update_cache() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info("Running update_cache")

    # ----- logic ----- #
    course.storage_api.update_cached_scores()

    return "", 200


@bp.get("/solutions")
@requires_token
@requires_ready
def get_solutions() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if "task" not in request.form:
        return "You didn't provide required attribute `task`", 400
    task_name = request.form["task"]

    # TODO: parameter to return not aggregated solutions

    # ----- logic ----- #
    try:
        _, _ = course.deadlines.find_task(task_name)
    except KeyError:
        return f"There is no task with name `{task_name}` (or it is disabled)", 404

    zip_bytes_io = course.solutions_api.get_task_aggregated_zip_io(task_name)
    if not zip_bytes_io:
        return f"Unable to get zip for {task_name}", 500

    _now_str = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
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

