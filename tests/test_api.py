import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from dotenv import load_dotenv
from flask import Flask, json

from manytask.api import _parse_flags, _update_score, bp as api_bp
from manytask.web import bp as web_bp


# Constants
TEST_USER_ID = 123
TEST_USERNAME = "test_user"
INVALID_TASK_NAME = "invalid_task"
TEST_TASK_NAME = "test_task"
TEST_SECRET_KEY = "test_key"


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    load_dotenv()
    if not os.getenv('TESTER_TOKEN'):
        monkeypatch.setenv('TESTER_TOKEN', 'test_token')
    monkeypatch.setenv('FLASK_SECRET_KEY', 'test_key')
    monkeypatch.setenv('TESTING', 'true')
    yield


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['DEBUG'] = False
    app.config['TESTING'] = True
    app.secret_key = TEST_SECRET_KEY
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    return app


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.config = {"test": "config"}
            self.deadlines = MockDeadlines()
            self.storage_api = self.storage_api()
            self.solutions_api = MockSolutionsApi()
            self.gitlab_api = self.gitlab_api()
            self.debug = False

        class storage_api:
            def __init__(self):
                self.scores = {}

            def store_score(self, student, task_name, update_fn):
                old_score = self.scores.get(f"{student.username}_{task_name}", 0)
                new_score = update_fn("", old_score)
                self.scores[f"{student.username}_{task_name}"] = new_score
                return new_score

            @staticmethod
            def get_scores(_username):
                return {"task1": 100, "task2": 90, "test_task": 80}

            @staticmethod
            def get_stored_user(student):
                from manytask.abstract import StoredUser
                return StoredUser(username=student.username, course_admin=True)

        class gitlab_api:
            @staticmethod
            def get_student(user_id):
                if user_id == TEST_USER_ID:
                    return MockStudent(TEST_USER_ID, TEST_USERNAME)
                raise Exception("Student not found")

            @staticmethod
            def get_student_by_username(username):
                if username == TEST_USERNAME:
                    return MockStudent(TEST_USER_ID, TEST_USERNAME)
                raise Exception("Student not found")

            @staticmethod
            def get_url_for_repo(username):
                return f"https://gitlab.com/{username}/test-repo"

    class MockSolutionsApi:
        def store_task_from_folder(self, task_name, username, folder_path):
            pass

    class MockDeadlines:
        def __init__(self):
            self.timezone = "UTC"

        @staticmethod
        def get_now_with_timezone():
            return datetime.now(tz=ZoneInfo("UTC"))

        @staticmethod
        def find_task(task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            return MockGroup(), MockTask()

    class MockStudent:
        def __init__(self, student_id, username):
            self.id = student_id
            self.username = username

    class MockGroup:
        @staticmethod
        # pylint: disable=unused-argument
        def get_current_percent_multiplier(now):
            return 1.0

    class MockTask:
        def __init__(self):
            self.name = TEST_TASK_NAME
            self.score = 100

    return MockCourse()


@pytest.fixture
def authenticated_client(app):
    """
    Provides a client with anauthenticated session
    """
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['gitlab'] = {
                "version": 1.5,
                "username": TEST_USERNAME,
                "user_id": TEST_USER_ID,
                "repo": "test_repo",
                "course_admin": False
            }
        yield client


def test_parse_flags_no_flags():
    assert _parse_flags(None) == timedelta()
    assert _parse_flags("") == timedelta()


def test_parse_flags_valid():
    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    flags = f"flag:3:{future_date}"
    assert _parse_flags(flags) == timedelta(days=3)


def test_parse_flags_past_date():
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    flags = f"flag:3:{past_date}"
    assert _parse_flags(flags) == timedelta()


def test_update_score_basic(mock_course):
    group = mock_course.deadlines.find_task("test_task")[0]
    task = mock_course.deadlines.find_task("test_task")[1]
    score = _update_score(group, task, 80, "", 0, datetime.now(tz=ZoneInfo("UTC")))
    assert score == 80


def test_update_score_with_old_score(mock_course):
    group = mock_course.deadlines.find_task("test_task")[0]
    task = mock_course.deadlines.find_task("test_task")[1]
    score = _update_score(group, task, 70, "", 80, datetime.now(tz=ZoneInfo("UTC")))
    assert score == 80  # Should keep higher old score


def test_healthcheck(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get('/api/healthcheck')
        assert response.status_code == 200
        assert response.data == b'OK'


def test_report_score_missing_task(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {'user_id': str(TEST_USER_ID)}
        headers = {'Authorization': f'Bearer {os.environ["TESTER_TOKEN"]}'}

        response = app.test_client().post('/api/report',
                                          data=data,
                                          headers=headers)
        assert response.status_code == 400
        assert b'task' in response.data


def test_report_score_missing_user(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {'task': TEST_TASK_NAME}
        headers = {'Authorization': f'Bearer {os.environ["TESTER_TOKEN"]}'}

        response = app.test_client().post('/api/report',
                                          data=data,
                                          headers=headers)
        assert response.status_code == 400
        assert b'user_id' in response.data


def test_report_score_invalid_task(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {'task': INVALID_TASK_NAME, 'user_id': str(TEST_USER_ID)}
        headers = {'Authorization': f'Bearer {os.environ["TESTER_TOKEN"]}'}

        response = app.test_client().post('/api/report',
                                          data=data,
                                          headers=headers)
        assert response.status_code == 404


def test_report_score_success(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {
            'task': TEST_TASK_NAME,
            'user_id': str(TEST_USER_ID),
            'score': '90',
            'check_deadline': 'True'
        }
        headers = {'Authorization': f'Bearer {os.environ["TESTER_TOKEN"]}'}
        expected_data = {
            'username': TEST_USERNAME,
            'score': 90
        }

        response = app.test_client().post('/api/report',
                                          data=data,
                                          headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['username'] == expected_data['username']
        assert data['score'] == expected_data['score']


def test_get_score_success(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {
            'task': TEST_TASK_NAME,
            'username': TEST_USERNAME
        }
        headers = {'Authorization': f'Bearer {os.environ["TESTER_TOKEN"]}'}
        expected_data = {
            'score': 80,
            'task': TEST_TASK_NAME,
            'user_id': TEST_USER_ID,
            'username': TEST_USERNAME
        }

        response = app.test_client().get('/api/score',
                                         data=data,
                                         headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == expected_data


def test_update_database_not_json(app, mock_course, authenticated_client):
    app.course = mock_course
    response = authenticated_client.post('/api/database/update',
                                         data='not json',
                                         content_type='text/plain')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Request must be JSON' in data['message']


def test_update_database_missing_fields(app, mock_course, authenticated_client):
    app.course = mock_course

    # Empty data
    response = authenticated_client.post('/api/database/update',
                                         json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Missing required fields' in data['message']

    # Partial data
    response = authenticated_client.post('/api/database/update',
                                         json={'username': TEST_USERNAME})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Missing required fields' in data['message']


def test_update_database_success(app, mock_course, authenticated_client):
    app.course = mock_course
    test_data = {
        'username': TEST_USERNAME,
        'scores': {
            'task1': 90,
            'task2': 85
        }
    }
    response = authenticated_client.post('/api/database/update',
                                         json=test_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


def test_update_database_invalid_score_type(app, mock_course, authenticated_client):
    app.course = mock_course
    test_data = {
        'username': TEST_USERNAME,
        'scores': {
            'task1': 'not a number',  # invalid score type
            'task2': 85
        }
    }
    response = authenticated_client.post('/api/database/update',
                                         json=test_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


def test_update_database_unauthorized(app, mock_course):
    app.course = mock_course
    test_data = {
        'username': TEST_USERNAME,
        'scores': {
            'task1': 90,
            'task2': 85
        }
    }
    response = app.test_client().post('/api/database/update',
                                      json=test_data)
    # Signup
    assert response.status_code == 302


def test_update_database_not_ready(app, mock_course, authenticated_client):
    mock_course.config = None
    app.course = mock_course
    test_data = {
        'username': TEST_USERNAME,
        'scores': {
            'task1': 90,
            'task2': 85
        }
    }
    response = authenticated_client.post('/api/database/update',
                                         json=test_data)
    # Not ready
    assert response.status_code == 302
