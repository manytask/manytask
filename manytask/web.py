import logging
import secrets
from collections import defaultdict

import gitlab
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import (Blueprint, current_app, redirect, render_template, request,
                   session, url_for)

from . import glab
from .course import Course, Task
from .glab import Student

SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint('web', __name__)


def valid_session(user_session: session) -> bool:
    return (
        'gitlab' in user_session
        and 'version' in user_session['gitlab']
        and user_session['gitlab']['version'] >= SESSION_VERSION
        and 'username' in user_session['gitlab']
        and 'user_id' in user_session['gitlab']
        and 'repo' in user_session['gitlab']
        and 'course_admin' in user_session['gitlab']
    )


@bp.route('/')
def course_page():
    course: Course = current_app.course

    if current_app.debug:
        student_username = 'guest'
        student_repo = course.gitlab_api.get_url_for_repo(student_username)
        student_course_admin = request.args.get('admin', None) is not None
    else:
        if not valid_session(session):
            return redirect(url_for('web.signup'))
        student_username = session['gitlab']['username']
        student_repo = session['gitlab']['repo']
        student_course_admin = session['gitlab']['course_admin']

    rating_table = course.rating_table
    review_table = course.review_table
    if course.debug:
        rating_table.update_cached_scores()
        review_table.update_cached_reviews()
    tasks_scores = rating_table.get_scores(student_username)
    all_task_reviews = review_table.get_reviews()

    task_reviews = defaultdict(list)
    for student, student_reviews in all_task_reviews.items():
        for task_name, task_review_score in student_reviews.items():
            task_reviews[task_name].append(int(task_review_score))
    print('! task_reviews', task_reviews)

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
        task_reviews=task_reviews,
        course_favicon=course.favicon
    )


@bp.route('/reviews', methods=['GET', 'POST'])
def review_page():
    course: Course = current_app.course

    if current_app.debug:
        student_username = 'guest'
        student_user_id = 0
        student_repo = course.gitlab_api.get_url_for_repo(student_username)
        student_course_admin = request.args.get('admin', None) is not None
    else:
        if not valid_session(session):
            return redirect(url_for('web.signup'))
        student_username = session['gitlab']['username']
        student_user_id = int(session['gitlab']['user_id'])
        student_repo = session['gitlab']['repo']
        student_course_admin = session['gitlab']['course_admin']

    rating_table = course.rating_table
    review_table = course.review_table
    if course.debug:
        rating_table.update_cached_scores()
        review_table.update_cached_reviews()
    tasks_scores = rating_table.get_scores(student_username)
    all_task_reviews = review_table.get_reviews()

    student_reviews = all_task_reviews.get(student_username, {})

    # ---- process review ---- #
    if request.method == 'POST':
        if current_app.debug:
            student = Student(
                id=student_user_id, username=student_username, name='Guest', course_admin=student_course_admin
            )
        else:
            try:
                student = course.gitlab_api.get_student(student_user_id)
            except Exception:
                return f'There is no student with user_id {student_user_id}', 404

        print('request.form', request.form)
        new_or_updated_scores: dict[str, int] = {}
        for task_name, review_score in request.form.items():
            # check review score is valid
            try:
                review_score_int = int(review_score)
            except ValueError:
                continue

            # check task solved
            if task_name not in tasks_scores:
                continue

            # collect updated scores
            if task_name not in student_reviews or student_reviews[task_name] != review_score_int:
                new_or_updated_scores[task_name] = review_score_int

        # insert new review scores
        print('new_or_updated_scores', new_or_updated_scores)
        if new_or_updated_scores:
            review_table.store_reviews(student, new_or_updated_scores)
        print('new_or_updated_scores end')

        return redirect(
            url_for('web.review_page')
        )

    # ---- render page ---- #

    task_reviews = defaultdict(list)
    for student, student_reviews in all_task_reviews.items():
        for task_name, task_review_score in student_reviews.items():
            task_reviews[task_name].append(int(task_review_score))
    print('! task_reviews', task_reviews)

    return render_template(
        'reviews.html',
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
        reviews=student_reviews,
        task_reviews=task_reviews,
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
        course.googledoc_api.fetch_private_accounts_table().add_user_row(user, student)
    except Exception as e:
        logger.exception(f'Could not write user data to private google doc, data: {user.__dict__}, {student.__dict__}')
        logger.exception(f'Writing private google doc failed: {e}')

    return redirect(
        url_for('web.login')
    )


@bp.route('/login', methods=['GET'])
def login():
    """Only way to login - gitlab oauth"""
    oauth: OAuth = current_app.oauth

    redirect_uri = url_for('web.login_finish', _external=True)

    return oauth.gitlab.authorize_redirect(redirect_uri)


@bp.route('/login_finish')
def login_finish():
    """Callback for gitlab oauth"""
    course: Course = current_app.course
    oauth: OAuth = current_app.oauth

    # ----- get args ----- #
    is_create_project = True
    if 'nocreate' in request.args:
        is_create_project = False
    if 'not_create_project' in request.args:
        is_create_project = False

    # ----- oauth authorize ----- #
    try:
        gitlab_oauth_token = oauth.gitlab.authorize_access_token()
    except OAuthError:
        return redirect(url_for('web.login'))

    gitlab_access_token: str = gitlab_oauth_token['access_token']
    gitlab_refresh_token: str = gitlab_oauth_token['refresh_token']
    gitlab_openid_user = oauth.gitlab.parse_id_token(gitlab_oauth_token, claims_options={'iss': {'essential': False}})

    # get oauth student
    # TODO do not return 502 (raise_for_status below)
    student = course.gitlab_api.get_authenticated_student(gitlab_access_token)

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
        'oauth_access_token': gitlab_access_token,
        'oauth_refresh_token': gitlab_refresh_token,
        'username': student.username,
        'user_id': student.id,
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
