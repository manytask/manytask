import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from flask import Flask, url_for
from pydantic import AnyUrl

from manytask.abstract import StoredUser
from manytask.config import ManytaskConfig, ManytaskDeadlinesConfig, ManytaskSettingsConfig, ManytaskUiConfig
from manytask.glab import Student
from manytask.web import bp as web_bp, get_allscores_url


TEST_USERNAME = "test_user"
TEST_SECRET = "test_secret"
TEST_KEY = "test_key"
TEST_TOKEN = "test_token"
TEST_COURSE_NAME = "Test Course"
GITLAB_BASE_URL = "https://gitlab.com"
TEST_VERSION = 1.5
TEST_USER_ID = 123
TEST_REPO = "test_repo"


@pytest.fixture
def app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'manytask/templates'))
    app.config['DEBUG'] = False
    app.config['TESTING'] = True
    app.secret_key = 'test_key'
    app.register_blueprint(web_bp)
    return app


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.name = TEST_COURSE_NAME
            self.config = ManytaskConfig(
                version=1,
                settings=ManytaskSettingsConfig(
                    course_name=TEST_COURSE_NAME,
                    gitlab_base_url=AnyUrl(GITLAB_BASE_URL),
                    public_repo="test/repo",
                    students_group="test/students"
                ),
                ui=ManytaskUiConfig(
                    task_url_template=f"{GITLAB_BASE_URL}/test/$GROUP_NAME/$TASK_NAME",
                    links={}
                ),
                deadlines=ManytaskDeadlinesConfig(
                    timezone="UTC",
                    schedule=[]
                )
            )
            self.show_allscores = True
            self.manytask_version = "1.0.0"
            self.favicon = "test_favicon"
            self.registration_secret = TEST_SECRET
            self.debug = False
            self.deadlines = self.MockDeadlines()
            self.storage_api = self.storage_api()
            self.viewer_api = self.viewer_api()
            self.gitlab_api = self.gitlab_api()
            self.solutions_api = self.MockSolutionsApi()

        class MockDeadlines:
            @staticmethod
            def get_now_with_timezone():
                return datetime.now(tz=ZoneInfo("UTC"))

            @staticmethod
            def get_groups():
                return []

            @property
            def max_score_started(self):
                return 100  # Mock value for testing

        class gitlab_api:
            def __init__(self):
                self.course_admin = False

            @staticmethod
            def get_url_for_repo(username):
                return f"{GITLAB_BASE_URL}/{username}/repo"

            @staticmethod
            def get_url_for_task_base():
                return f"{GITLAB_BASE_URL}/tasks"

            @staticmethod
            def register_new_user(user):
                if user.username == TEST_USERNAME:
                    return True
                raise Exception("Registration failed")

            @staticmethod
            def get_student(_user_id):
                return Student(id=TEST_USER_ID, username=TEST_USERNAME, name='')

            def get_authenticated_student(self, _gitlab_access_token):
                return Student(id=TEST_USER_ID, username=TEST_USERNAME, name='', course_admin=self.course_admin)

            @staticmethod
            def check_project_exists(_student):
                return True

            base_url = GITLAB_BASE_URL

        class storage_api:
            def __init__(self):
                self.stored_user = StoredUser(username=TEST_USERNAME, course_admin=False)

            @staticmethod
            def get_scores_update_timestamp():
                return datetime.now(tz=ZoneInfo("UTC"))

            @staticmethod
            def get_scores(_username):
                return {"task1": 100, "task2": 90}

            @staticmethod
            def get_all_scores():
                return {TEST_USERNAME: {"task1": 100, "task2": 90}}

            @staticmethod
            def get_stats():
                return {"task1": {"mean": 95}, "task2": {"mean": 85}}

            @staticmethod
            def get_bonus_score(_username):
                return 10

            def sync_stored_user(self, student):
                if student.course_admin:
                    self.stored_user.course_admin = True

            def get_stored_user(self, _student):
                return self.stored_user

            @staticmethod
            def update_cached_scores():
                pass

        class viewer_api:
            @staticmethod
            def get_scoreboard_url():
                return "https://docs.google.com/spreadsheets"

        class MockSolutionsApi:
            def store_task_from_folder(self, task_name, username, folder_path):
                pass

    return MockCourse()


@pytest.fixture
def mock_gitlab_oauth():
    class MockGitlabOauth:
        class gitlab:
            @staticmethod
            def authorize_access_token():
                return {"access_token": "", "refresh_token": ""}

    return MockGitlabOauth()


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    monkeypatch.setenv('TESTER_TOKEN', TEST_TOKEN)
    monkeypatch.setenv('REGISTRATION_SECRET', TEST_SECRET)
    monkeypatch.setenv('FLASK_SECRET_KEY', TEST_KEY)
    monkeypatch.setenv('TESTING', 'true')
    yield


def test_course_page_not_ready(app, mock_course):
    mock_course.config = None
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get('/')
        assert response.status_code == 302
        assert response.headers['Location'] == '/not_ready'


def test_course_page_invalid_session(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get('/')
        assert response.status_code == 302
        assert response.headers['Location'] == '/signup'


def test_course_page_valid_session(app, mock_course):
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['gitlab'] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "oauth_access_token": TEST_TOKEN,
                }
            app.course = mock_course
            response = client.get('/')
            assert response.status_code == 200


def test_signup_get(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get('/signup')
        assert response.status_code == 200


def test_signup_post_invalid_secret(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().post('/signup', data={
            'username': TEST_USERNAME,
            'firstname': 'Test',
            'lastname': 'User',
            'email': 'test@example.com',
            'password': 'password123',
            'password2': 'password123',
            'secret': 'wrong_secret'
        })
        assert response.status_code == 200
        assert b'Invalid registration secret' in response.data


def test_signup_post_password_mismatch(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().post('/signup', data={
            'username': TEST_USERNAME,
            'firstname': 'Test',
            'lastname': 'User',
            'email': 'test@example.com',
            'password': 'password123',
            'password2': 'password456',
            'secret': mock_course.registration_secret
        })
        assert response.status_code == 200
        assert b'Passwords don&#39;t match' in response.data


def test_logout(app):
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['gitlab'] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME
                }
            response = client.get('/logout')
            assert response.status_code == 302
            assert response.headers['Location'] == '/'
            with client.session_transaction() as sess:
                assert 'gitlab' not in sess


def test_not_ready(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get('/not_ready')
        assert response.status_code == 302

def test_get_allscores_url(app, mock_course):
    with app.test_request_context():
        test_url = "https://docs.google.com/spreadsheets"
        class viewer_api_gsheets:
            @staticmethod
            def get_scoreboard_url():
                return test_url
            
        class viewer_api_db:
            @staticmethod
            def get_scoreboard_url():
                return ""
        assert get_allscores_url(viewer_api_gsheets) == test_url
        assert get_allscores_url(viewer_api_db) == url_for('web.show_database')

def check_admin_in_data(response, check_true):
    assert response.status_code == 200
    if check_true:
        assert b'class="admin-label' in response.data
    else:
        assert b'class="admin-label' not in response.data


def check_admin_status_code(response, check_true):
    if check_true:
        assert response.status_code != 403
    else:
        assert response.status_code == 403


@pytest.mark.parametrize("path_and_func", [
    ['/', check_admin_in_data],
    ['/solutions', check_admin_status_code],
    ['/database', check_admin_in_data]
])
@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("get_param_admin", ['true', '1', 'yes', None, 'false', '0', 'no', 'random_value'])
def test_course_page_user_sync(app, mock_course, path_and_func, debug, get_param_admin):
    path, check_func = path_and_func

    if get_param_admin is not None:
        path += f'?admin={get_param_admin}'

    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['gitlab'] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "oauth_access_token": TEST_TOKEN,
                }
                sess['course'] = {
                    "secret": TEST_SECRET,
                }
            app.course = mock_course
            app.debug = debug

            # not admin in gitlab, not admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ('true', '1', 'yes', None))
            else:
                check_func(response, False)

            with client.session_transaction() as sess:
                sess['gitlab'] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": True,
                    "oauth_access_token": TEST_TOKEN,
                }
                sess['course'] = {
                    "secret": TEST_SECRET,
                }

            # admin in gitlab, not admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ('true', '1', 'yes', None))
            else:
                check_func(response, True)

            with client.session_transaction() as sess:
                sess['gitlab'] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "oauth_access_token": TEST_TOKEN,
                }
                sess['course'] = {
                    "secret": TEST_SECRET,
                }

            app.course.storage_api.stored_user.course_admin = True

            # not admin in gitlab, admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ('true', '1', 'yes', None))
            else:
                check_func(response, True)

            with client.session_transaction() as sess:
                sess['gitlab'] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "oauth_access_token": TEST_TOKEN,
                }
                sess['course'] = {
                    "secret": TEST_SECRET,
                }

            # admin in gitlab, admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ('true', '1', 'yes', None))
            else:
                check_func(response, True)


def test_login_finish_sync(app, mock_course, mock_gitlab_oauth):
    with app.test_request_context():
        with app.test_client() as client:
            app.course = mock_course
            app.oauth = mock_gitlab_oauth

            assert not app.course.storage_api.stored_user.course_admin

            # not admin in gitlab so stored value shouldn't change
            client.get('/login_finish')

            with client.session_transaction() as sess:
                assert 'gitlab' in sess
                assert not sess["gitlab"]["course_admin"]

            assert not app.course.storage_api.stored_user.course_admin

            app.course.gitlab_api.course_admin = True

            # admin in gitlab so stored value should change
            client.get('/login_finish')

            with client.session_transaction() as sess:
                assert 'gitlab' in sess
                assert sess["gitlab"]["course_admin"]

            assert app.course.storage_api.stored_user.course_admin

            app.course.gitlab_api.course_admin = False

            # not admin in gitlab but also stored that admin
            client.get('/login_finish')

            with client.session_transaction() as sess:
                assert 'gitlab' in sess
                assert not sess["gitlab"]["course_admin"]

            assert app.course.storage_api.stored_user.course_admin
