import logging
import secrets
import uuid

from flask import session, redirect, request, render_template, current_app, url_for, Blueprint
import gitlab

from . import glab
from .course import Course, Task
from .glab import map_gitlab_user_to_student

SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint('web', __name__)


def valid_session(user_session: session) -> bool:
    return (
        'gitlab' in user_session
        and 'version' in user_session['gitlab']
        and user_session['gitlab']['version'] >= SESSION_VERSION
        and 'username' in user_session['gitlab']
        and 'repo' in user_session['gitlab']
        and 'course_admin' in user_session['gitlab']
    )


@bp.route('/')
def course_page():
    course: Course = current_app.course

    if current_app.debug:
        student_username = 'guest'
        student_repo = course.gitlab_api.get_url_for_repo(student_username)
        student_course_admin = True
    else:
        if not valid_session(session):
            return redirect(url_for('course_page.signup'))
        student_username = session['gitlab']['username']
        student_repo = session['gitlab']['repo']
        student_course_admin = session['gitlab']['course_admin']

    if current_app.debug:
        tasks: list[Task] = []
        for group in course.deadlines.open_groups:
            tasks.extend(group.tasks)
        tasks_scores = course.rating_table.get_scores_debug(tasks)
    else:
        tasks_scores = course.rating_table.get_scores(student_username)

    return render_template(
        'tasks.html',
        task_base_url=course.gitlab_api.get_url_for_task_base(),
        username=student_username,
        course_name=course.name,
        current_course=course,
        student_repo_url=student_repo,
        student_ci_url=f'{student_repo}/pipelines',
        gdoc_url=course.googledoc_api.get_spreadsheet_url(),
        lms_url=course.lms_url,
        tg_invite_link=course.tg_invite_link,
        scores=tasks_scores,
        course_favicon=course.favicon
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
    course: Course = current_app.course

    # ----- get args ----- #
    is_create_project = True
    if 'nocreate' in request.args:
        is_create_project = False
    if 'not_create_project' in request.args:
        is_create_project = False

    request_state = request.args['state']

    code = request.args['code']

    # ----- Oauth login finish ----- #
    # Check state we sent earlier to prevent CSRF attack
    state = session.pop('state', None)
    if state is None or request_state != state:
        return redirect(url_for('web.login'))

    # get oauth student
    redirect_uri = url_for('web.login_finish', _external=True)
    # TODO do not return 502 (raise_for_status below)
    gitlab_token = course.gitlab_api.get_oauth_token(redirect_uri, code)
    student = course.gitlab_api.get_authenticated_student(gitlab_token)

    # Create use if needed
    if is_create_project and not current_app.debug:
        try:
            course.gitlab_api.create_project(student)
        except gitlab.GitlabError as ex:
            logger.error(f'Project creation failed: {ex.error_message}')
            return render_template(
                'signup.html',
                error_message=ex.error_message,
                course_name=course.name
            )

    # save user in session
    session['gitlab'] = {
        'oauth_token': gitlab_token,
        'username': student.username,
        'course_admin': student.course_admin,
        'repo': student.repo,
        'version': SESSION_VERSION,
    }
    session.permanent = True

    return redirect(url_for('web.course_page'))


@bp.route('/logout')
def logout():
    session.pop('gitlab', None)
    return redirect(url_for('web.course_page'))
