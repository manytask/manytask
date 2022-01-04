import logging
import secrets
import uuid

from flask import Blueprint
from flask import session, redirect, request, render_template, current_app, url_for, Blueprint


logger = logging.getLogger(__name__)
bp = Blueprint('web', __name__)


@bp.route('/')
def course_page():
    return {'session_gitlab': session['gitlab']}
    return render_template(
        'tasks.html',
    )


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    return {}, 500
    return render_template(
        'signup.html',
    )


@bp.route('/login', methods=['GET'])
def login():
    """Only way to login - gitlab oauth"""

    redirect_uri = url_for('web.login_finish', _external=True)

    state = secrets.token_urlsafe(32)
    session['state'] = state

    return redirect(
        ''
    )


@bp.route('/login_finish')
def login_finish():
    """Callback for gitlab oauth"""

    # Check state we sent earlier to prevent CSRF attack
    request_state = request.args['state']
    state = session.pop('state', None)
    if state is None or request_state != state:
        return redirect(url_for('web.login'))

    return redirect(url_for('web.course_page'))


@bp.route('/logout')
def logout():
    session.pop('gitlab', None)
    return redirect(url_for('web.course_page'))
