from __future__ import annotations

import functools
import logging
import os
import secrets
from datetime import datetime, timedelta

import yaml
from flask import Blueprint, abort, current_app, request

from manytask.course import (Course, Task, get_current_time,
                             validate_commit_time)


logger = logging.getLogger(__name__)
bp = Blueprint('api', __name__, url_prefix='/api')


TESTER_TOKEN = os.environ['TESTER_TOKEN']


def requires_token(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.form.get('token', request.headers.get('Authorization', ''))
        if not token:
            abort(403)
        token = token.split()[-1]
        if not secrets.compare_digest(token, TESTER_TOKEN):
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
            parsed = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            logger.error(f'Could not parse date from flag {flags}')
        if parsed is not None and datetime.now() <= parsed:
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
        demand_multiplier: float = 1.
) -> int:
    if old_score < 0:
        return old_score

    assert 0 <= demand_multiplier <= 2

    extra_time = _parse_flags(flags)

    if task.scoring_func == 'max':
        if check_deadline and task.is_overdue_second(extra_time, submit_time=submit_time):
            new_score = 0
        elif check_deadline and task.is_overdue(extra_time, submit_time=submit_time):
            new_score = int(0.5 * score * demand_multiplier)
        else:
            new_score = int(score * demand_multiplier)
        return max(new_score, old_score)
    elif task.scoring_func == 'latest':
        if check_deadline and task.is_overdue_second(extra_time, submit_time=submit_time):
            return old_score
        if check_deadline and task.is_overdue(extra_time, submit_time=submit_time):
            return int(0.5 * score * demand_multiplier)
        return int(score * demand_multiplier)
    else:
        raise ValueError(f'Wrong scoring func: {task.scoring_func}')


@bp.post('/report')
@requires_token
def report_score():
    course: Course = current_app.course

    # ----- get and validate request parameters ----- #
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    check_deadline = False
    if 'check_deadline' in request.form:
        check_deadline = request.form['check_deadline'] is True or request.form['check_deadline'] == 'True'

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

    tasks_demands = course.rating_table.get_demands()
    task_demand_multiplier = tasks_demands.get(task_name, 1)

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
        f'Verify deadline: current_time={current_time} and commit_time={commit_time}. Got submit_time={submit_time}'
    )

    logger.info(f'task {task.name} score {reported_score} check_deadline {check_deadline}')
    update_function = functools.partial(
        _update_score, task, reported_score,
        submit_time=submit_time, check_deadline=check_deadline, demand_multiplier=task_demand_multiplier,
    )
    final_score = course.rating_table.store_score(student, task.name, update_function)

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
def get_score():
    course: Course = current_app.course

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


@bp.post('/update_task_columns')
@requires_token
def update_task_columns():
    course: Course = current_app.course

    logger.info(f'Running update_task_columns')

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


@bp.post('/sync_task_columns')
@requires_token
def sync_task_columns():
    course: Course = current_app.course

    logger.info(f'Running sync_task_columns')

    # ----- get and validate request parameters ----- #
    try:
        course.store_deadlines(request.get_json(force=True, silent=False))
    except Exception as e:
        logger.exception(e)
        return 'Invalid deadlines', 400

    # ----- logic ----- #
    # sync columns
    tasks_started = course.deadlines.tasks_started
    max_score_started = course.deadlines.max_score_started
    course.rating_table.sync_columns(tasks_started, max_score_started)

    return '', 200


@bp.post('/update_cached_scores')
@requires_token
def update_cached_scores():
    course: Course = current_app.course

    logger.info(f'Running update_cached_scores')

    # ----- logic ----- #
    course.rating_table.update_cached_scores()

    return '', 200


@bp.post('/report_source')
@requires_token
def report_source():
    course: Course = current_app.course

    # ----- get and validate request parameters ----- #
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    if 'files' not in request.files.getlist:
        return 'You didn\'t provide required attribute `files`', 400
    files = request.files.getlist('files')

    # ----- logic ----- #
    for file in files:
        print('file', file)
        # file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))

    pass


@bp.get('/solutions')
@requires_token
def get_solutions():
    course: Course = current_app.course

    # ----- get and validate request parameters ----- #
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    # ----- logic ----- #

    pass

