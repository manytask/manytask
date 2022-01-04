from __future__ import annotations

import functools
import logging
import os
import secrets
from datetime import datetime

from flask import request, abort, current_app, Blueprint


logger = logging.getLogger(__name__)
bp = Blueprint('api', __name__, url_prefix='/api')


TESTER_TOKEN = os.environ['TESTER_TOKEN']


def requires_token(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.form.get('token', request.headers.get('Authorization', ''))
        token = token.split()[-1]
        if not secrets.compare_digest(token, TESTER_TOKEN):
            abort(403)

        return f(*args, **kwargs)
    return decorated


@bp.post('/report')
@requires_token
def report_score():
    # get and validate request parameters
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    check_deadline = False
    if 'check_deadline' in request.form:
        check_deadline = request.form['check_deadline'] is True or request.form['check_deadline'] == 'True'

    score: int | None = None
    if 'score' in request.form:
        score_str = request.form['score']
        try:
            score = int(score_str)
        except ValueError:
            return f'Cannot parse `score` <{score}> to int`', 400

    commit_time = None
    if 'commit_time' in request.form:
        commit_time_str = request.form['commit_time']
        try:
            commit_time = datetime.strptime(commit_time_str, '%Y-%m-%d %H:%M:%S%z')
            # TODO: commit_time = commit_time.astimezone(MOSCOW_TIMEZONE)
        except ValueError:
            commit_time = None

    # logic

    pass


@bp.get('/score')
@requires_token
def get_score():
    # get and validate request parameters
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    # logic
    pass


@bp.post('/sync_task_columns')
@requires_token
def sync_task_columns():
    pass


@bp.post('/update_cached_scores')
@requires_token
def update_cached_scores():
    pass


@bp.post('/report_source')
@requires_token
def report_source():
    # get and validate request parameters
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    if 'user_id' not in request.form:
        return 'You didn\'t provide required attribute `user_id`', 400
    user_id = int(request.form['user_id'])

    if 'files' not in request.files.getlist:
        return 'You didn\'t provide required attribute `files`', 400
    files = request.files.getlist('files')

    # logic
    for file in files:
        print('file', file)
        # file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))

    pass


@bp.get('/solutions')
@requires_token
def get_solutions():
    # get and validate request parameters
    if 'task' not in request.form:
        return 'You didn\'t provide required attribute `task`', 400
    task_name = request.form['task']

    # logic

    pass

