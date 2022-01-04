import logging
import secrets
import uuid

from flask import session, redirect, request, render_template, current_app, url_for, Blueprint
import gitlab

from . import glab
from .course import Course
from .glab import map_gitlab_user_to_student

SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint('web', __name__)


def valid_session(user_session: session) -> bool:
    return (
        'gitlab' in user_session
        and user_session['gitlab']['version'] >= SESSION_VERSION
        and 'username' in user_session['gitlab']
        and 'repo' in user_session['gitlab']
        and 'admin' in user_session['gitlab']
    )


@bp.route('/')
def course_page():
    return {'session_gitlab': session['gitlab']}
    return render_template(
        'tasks.html',
    )


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    course: Course = current_app.course

    # ---- render page ---- #
    if request.method == 'GET':
        return render_template(
            'signup.html',
            course_name=course.name,
            course_favicon=course.favicon
        )

    # ----  register a new user ---- #
    # render template with error... if error
    user = glab.User(
        request.form['username'].strip(),
        request.form['firstname'].strip(),
        request.form['lastname'].strip(),
        request.form['email'].strip(),
        request.form['password'],
        request.form['telegram'],
        request.form['lms_id'],
    )

    try:
        if not secrets.compare_digest(request.form['secret'], course.registration_secret):
            raise Exception('Invalid registration secret')
        registered_user = course.gitlab_api.register_new_user(user)
    except Exception as e:
        logger.exception(f'User registration failed: {e}')
        return render_template(
            'signup.html',
            error_message=str(e),
            course_name=course.name,
            course_favicon=course.favicon
        )
    student = glab.map_gitlab_user_to_student(registered_user)
    try:
        course.googledoc_api.fetch_private_data_table().add_user_row(user, student)
    except Exception as e:
        logger.exception(f'Could not write user data to private google doc, data: {user.__dict__}, {student.__dict__}')
        logger.exception(f'Writing private google doc failed: {e}')

    return redirect(
        url_for('web.login')
    )


@bp.route('/login', methods=['GET'])
def login():
    """Only way to login - gitlab oauth"""
    course: Course = current_app.course

    redirect_uri = url_for('web.login_finish', _external=True)
    state = secrets.token_urlsafe(32)

    session['state'] = state
    return redirect(
        course.gitlab_api.get_authorization_url(redirect_uri, state)
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
