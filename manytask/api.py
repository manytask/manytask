from __future__ import annotations

import functools
import logging
import os
import secrets
import tempfile
import typing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import yaml
from flask import Blueprint, Response, abort, current_app, request
from flask.typing import ResponseReturnValue
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from manytask.course import Course, Task, get_current_time, validate_commit_time, MOSCOW_TIMEZONE

logger = logging.getLogger(__name__)
bp = Blueprint('api', __name__, url_prefix='/api')


TESTER_TOKEN = os.environ['TESTER_TOKEN']


def requires_token(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        token = request.form.get('token', request.headers.get('Authorization', ''))
        if not token:
            abort(403)
        token = token.split()[-1]
        if not secrets.compare_digest(token, TESTER_TOKEN):
            abort(403)

        return f(*args, **kwargs)
    return decorated


def requires_ready(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not current_app.course.course_config:  # type: ignore
            abort(403)

        return f(*args, **kwargs)
    return decorated


def _parse_flags(flags: str | None) -> timedelta:
    flags = flags or ''

    extra_time = timedelta()
    left_colon = flags.find(':')
    right_colon = flags.find(':', left_colon + 1)
    if right_colon > -1 and left_colon > 0:
        parsed = None
        date_string = flags[right_colon + 1:]
        try:
            parsed = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=MOSCOW_TIMEZONE)
        except ValueError:
            logger.error(f'Could not parse date from flag {flags}')
        if parsed is not None and get_current_time() <= parsed:
            days = int(flags[left_colon + 1:right_colon])
            extra_time = timedelta(days=days)
    return extra_time


def _update_score(
        task: Task,
        score: int,
        flags: str,
        old_score: int,
        submit_time: datetime | None = None,
        check_deadline: bool = True,
        second_deadline_max: float = 0.5,
        demand_multiplier: float = 1.
) -> int:
    if old_score < 0:
        return old_score

    assert 0 <= second_deadline_max <= 1.
    assert 0 <= demand_multiplier <= 2.

    extra_time = _parse_flags(flags)

    if task.scoring_func == 'max':
        if check_deadline and task.is_overdue_second(extra_time, submit_time=submit_time):
            new_score = 0
        elif check_deadline and task.is_overdue(extra_time, submit_time=submit_time):
            new_score = int(second_deadline_max * score * demand_multiplier)
        else:
            new_score = int(score * demand_multiplier)
        return max(new_score, old_score)
    elif task.scoring_func == 'latest':
        if check_deadline and task.is_overdue_second(extra_time, submit_time=submit_time):
            return old_score
        if check_deadline and task.is_overdue(extra_time, submit_time=submit_time):
            return int(second_deadline_max * score * demand_multiplier)
        return int(score * demand_multiplier)
    else:
        raise ValueError(f'Wrong scoring func: {task.scoring_func}')


@bp.post('/report')
@requires_token
@requires_ready
def report_score() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    check_deadline = True
    if 'check_deadline' in request.form:
        check_deadline = request.form['check_deadline'] is True or request.form['check_deadline'] == 'True'

    use_demand_multiplier = False
    if 'use_demand_multiplier' in request.form:
        use_demand_multiplier = \
            request.form['use_demand_multiplier'] is True or request.form['use_demand_multiplier'] == 'True'

    reported_score: int | None = None
    if 'score' in request.form:
        score_str = request.form['score']
        try:
            reported_score = int(score_str)
        except ValueError:
            return f'Cannot parse `score` <{reported_score}> to int`', 400

    commit_time = None
    if 'commit_time' in request.form:
        commit_time_str = request.form['commit_time']
        try:
            commit_time = datetime.strptime(commit_time_str, '%Y-%m-%d %H:%M:%S%z')
            # TODO: commit_time = commit_time.astimezone(MOSCOW_TIMEZONE)
        except ValueError:
            commit_time = None

    tasks_demands = course.rating_table.get_demands_multipliers(
        low_demand_bonus_bound=course.course_config.low_demand_bonus_bound,
        max_demand_multiplier=course.course_config.max_low_demand_bonus,
    )
    if use_demand_multiplier:
        task_demand_multiplier = tasks_demands.get(task_name, 1.)
    else:
        task_demand_multiplier = 1.

    files: dict[str, FileStorage] = request.files.to_dict()  # may be empty

    # ----- logic ----- #
    try:
        task = course.deadlines.find_task(task_name)
    except KeyError:
        return f'There is no task with name `{task_name}` (or it is closed for submission)', 404

    try:
        student = course.gitlab_api.get_student(user_id)
    except Exception:
        return f'There is no student with user_id {user_id}', 404

    current_time = get_current_time()
    submit_time = validate_commit_time(commit_time, current_time)

    logger.info(
        f'Save score {reported_score} for @{student} on task {task.name} \n'
        f'check_deadline {check_deadline} task_demand_multiplier {task_demand_multiplier}'
    )
    logger.info(
        f'verify deadline: current_time={current_time} and commit_time={commit_time}. Got submit_time={submit_time}'
    )

    if reported_score is None:
        reported_score = task.score
        logger.info(
            f'Got score=None; set max score for {task.name} of {task.score}'
        )
    assert reported_score is not None

    update_function = functools.partial(
        _update_score,
        task,
        reported_score,
        submit_time=submit_time,
        check_deadline=check_deadline,
        second_deadline_max=course.course_config.second_deadline_max,
        demand_multiplier=task_demand_multiplier,
    )
    final_score = course.rating_table.store_score(student, task.name, update_function)

    # save pushed files if sent
    with tempfile.TemporaryDirectory() as temp_folder:
        temp_folder = Path(temp_folder)
        for file in files.values():
            secured_filename = secure_filename(file.filename)
            file.save(temp_folder / secured_filename)
        course.solutions_api.store_task_from_folder(task_name, student.username, temp_folder)

    return {
        'user_id': student.id,
        'username': student.username,
        'task': task.name,
        'score': final_score,
        'demand_multiplier': task_demand_multiplier,
        'commit_time': commit_time.isoformat(sep=' ') if commit_time else 'None',
        'submit_time': submit_time.isoformat(sep=' '),
    }, 200


@bp.get('/score')
@requires_token
@requires_ready
def get_score() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    # ----- logic ----- #
    try:
        task = course.deadlines.find_task(task_name)
    except KeyError:
        return f'There is no task with name `{task_name}` (or it is closed for submission)', 404

    try:
        student = course.gitlab_api.get_student(user_id)
        student_scores = course.rating_table.get_scores(student.username)
    except Exception:
        return f'There is no student with user_id {user_id}', 404

    try:
        student_task_score = student_scores[task.name]
    except Exception:
        return f'Cannot get score for task {task.name} for {student.username}', 404

    return {
        'user_id': student.id,
        'username': student.username,
        'task': task.name,
        'score': student_task_score,
    }, 200


@bp.post('/update_deadlines')
@requires_token
def update_deadlines() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info('Running update_deadlines')

    # ----- get and validate request parameters ----- #
    try:
        deadlines_raw_data = request.get_data()
        deadlines_data = yaml.load(deadlines_raw_data, Loader=yaml.SafeLoader)
        course.store_deadlines(deadlines_data)
    except Exception as e:
        logger.exception(e)
        return 'Invalid deadlines', 400

    # ----- logic ----- #
    # sync columns
    tasks_started = course.deadlines.tasks_started
    max_score_started = course.deadlines.max_score_started
    course.rating_table.sync_columns(tasks_started, max_score_started)

    return '', 200


@bp.post('/update_course_config')
@requires_token
def update_course_config() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info('Running update_course_config')

    # ----- get and validate request parameters ----- #
    try:
        config_raw_data = request.get_data()
        config_data = yaml.load(config_raw_data, Loader=yaml.SafeLoader)
        course.store_course_config(config_data)
    except Exception as e:
        logger.exception(e)
        return f'Invalid course config\n {e}', 400

    # ----- logic ----- #
    # TODO: fix course config storing. may work one thread only =(

    return '', 200


# DEPRECATED
@bp.post('/sync_task_columns')
@requires_token
def sync_task_columns() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info('Running DEPRECATED sync_task_columns')

    # ----- get and validate request parameters ----- #
    try:
        deadlines_data = typing.cast(list[dict[str, Any]], request.get_json(force=True, silent=False))
        course.store_deadlines(deadlines_data)
    except Exception as e:
        logger.exception(e)
        return 'Invalid deadlines', 400

    # ----- logic ----- #
    # sync columns
    tasks_started = course.deadlines.tasks_started
    max_score_started = course.deadlines.max_score_started
    course.rating_table.sync_columns(tasks_started, max_score_started)

    return '', 200


@bp.post('/update_cache')
@requires_token
def update_cache() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    logger.info('Running update_cache')

    # ----- logic ----- #
    course.rating_table.update_cached_scores()

    return '', 200


@bp.get('/solutions')
@requires_token
@requires_ready
def get_solutions() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ----- get and validate request parameters ----- #
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    # TODO: parameter to return not aggregated solutions

    # ----- logic ----- #
    try:
        _ = course.deadlines.find_task(task_name)
    except KeyError:
        return f'There is no task with name `{task_name}` (or it is disabled)', 404

    zip_bytes_io = course.solutions_api.get_task_aggregated_zip_io(task_name)
    if not zip_bytes_io:
        return f'Unable to get zip for {task_name}', 500

    _now_str = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    filename = f'aggregated-solutions-{task_name}-{_now_str}.zip'

    return Response(
        zip_bytes_io.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )
