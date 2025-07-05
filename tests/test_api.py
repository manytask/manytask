import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import yaml
from dotenv import load_dotenv
from flask import Flask, json
from werkzeug.exceptions import HTTPException

from manytask.abstract import StoredUser
from manytask.api import _get_student, _parse_flags, _process_score, _update_score
from manytask.api import bp as api_bp
from manytask.database import DataBaseApi, TaskDisabledError
from manytask.glab import Student
from manytask.web import course_bp, root_bp

TEST_USER_ID = 123
TEST_USERNAME = "test_user"
TEST_FIRST_NAME = "Ivan"
TEST_LAST_NAME = "Ivanov"
TEST_NAME = "Ivan Ivanov"
INVALID_TASK_NAME = "invalid_task"
TASK_NAME_WITH_DISABLED_TASK_OR_GROUP = "disabled_task"
TEST_TASK_NAME = "test_task"
TEST_SECRET_KEY = "test_key"
TEST_COURSE_NAME = "Test_Course"


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    load_dotenv()
    if not os.getenv("MANYTASK_COURSE_TOKEN"):
        monkeypatch.setenv("MANYTASK_COURSE_TOKEN", "test_token")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_key")
    monkeypatch.setenv("TESTING", "true")
    yield


@pytest.fixture
def app(mock_storage_api, mock_gitlab_api):
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = TEST_SECRET_KEY
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    app.storage_api = mock_storage_api
    app.gitlab_api = mock_gitlab_api
    app.rms_api = mock_gitlab_api
    app.manytask_version = "1.0.0"
    app.favicon = "test_favicon"

    def store_config(course_name, content):
        pass

    app.store_config = store_config

    return app


@pytest.fixture
def mock_task():
    class MockTask:
        def __init__(self):
            self.name = TEST_TASK_NAME
            self.score = 100

    return MockTask()


@pytest.fixture
def mock_group(mock_task):
    class MockGroup:
        def __init__(self):
            self.tasks = [mock_task]

        @staticmethod
        def get_current_percent_multiplier(now):
            return 1.0

        def get_tasks(self):
            return self.tasks

    return MockGroup()


@pytest.fixture
def mock_student():
    class MockStudent:
        def __init__(self, student_id, username, name):
            self.id = student_id
            self.username = username
            self.name = name

    return MockStudent


@pytest.fixture
def mock_storage_api(mock_course, mock_task, mock_group):  # noqa: C901
    class MockStorageApi:
        def __init__(self):
            self.scores = {}
            self.stored_user = StoredUser(
                username=TEST_USERNAME, first_name=TEST_FIRST_NAME, last_name=TEST_LAST_NAME, course_admin=False
            )
            self.course_name = TEST_COURSE_NAME

        def store_score(self, _course_name, username, repo_name, task_name, update_fn):
            old_score = self.scores.get(f"{username}_{task_name}", 0)
            new_score = update_fn("", old_score)
            self.scores[f"{username}_{task_name}"] = new_score
            return new_score

        @staticmethod
        def get_scores(_course_name, _username):
            return {"task1": 100, "task2": 90, "test_task": 80}

        @staticmethod
        def get_course(_name):
            return mock_course

        def get_all_scores(course_name, self):
            return {"test_user": self.get_scores(course_name, "test_user")}

        @staticmethod
        def get_stored_user(_course_name, username):
            from manytask.abstract import StoredUser

            return StoredUser(username=username, first_name=first_name, last_name=last_name, course_admin=True)

        def update_cached_scores(self, _course_name):
            pass

        def sync_columns(self, _course_name, _deadlines):
            pass

        def update_task_groups_from_config(self, _course_name, _config_data):
            pass

        def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool:
            self.stored_user.course_admin = course_admin
            return self.stored_user.course_admin

        def check_user_on_course(self, *a, **k):
            return True

        @staticmethod
        def find_task(_course_name, task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            if task_name == TASK_NAME_WITH_DISABLED_TASK_OR_GROUP:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            return mock_group, mock_task

        @staticmethod
        def get_now_with_timezone(_course_name):
            return datetime.now(tz=ZoneInfo("UTC"))

        def get_groups(self, _course_name):
            return [mock_group]

    return MockStorageApi()


@pytest.fixture
def mock_gitlab_api(mock_student):
    class MockGitlabApi:
        def __init__(self):
            self.course_admin = False
            self._student_class = mock_student

        def get_student(self, user_id: int):
            if user_id == TEST_USER_ID:
                return self._student_class(TEST_USER_ID, TEST_USERNAME, TEST_NAME)
            raise Exception("Student not found")

        def get_student_by_username(self, username):
            if username == TEST_USERNAME:
                return self._student_class(TEST_USER_ID, TEST_USERNAME, TEST_NAME)
            raise Exception("Student not found")

        def get_authenticated_student(self, access_token):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        @staticmethod
        def get_url_for_repo(username, course_students_group):
            return f"https://gitlab.com/{username}/test-repo"

        @staticmethod
        def check_project_exists(_student, course_students_group):
            return True

    return MockGitlabApi()


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.course_name = TEST_COURSE_NAME
            self.is_ready = True
            self.show_allscores = True
            self.registration_secret = "test_secret"
            self.token = os.environ["MANYTASK_COURSE_TOKEN"]
            self.gitlab_course_group = "test_group"
            self.gitlab_course_public_repo = "public_2025_spring"
            self.gitlab_course_students_group = "students_2025_spring"
            self.gitlab_default_branch = "main"

    return MockCourse()


@pytest.fixture
def authenticated_client(app, mock_gitlab_oauth):
    """
    Provides a client with anauthenticated session
    """
    with (
        app.test_client() as client,
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(app.gitlab_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
    ):
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }
        with client.session_transaction() as session:
            session["gitlab"] = {
                "version": 1.5,
                "username": TEST_USERNAME,
                "user_id": TEST_USER_ID,
                "access_token": "",
                "refresh_token": "",
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


def test_update_score_basic(app):
    group = app.storage_api.find_task(TEST_COURSE_NAME, "test_task")[0]
    task = app.storage_api.find_task(TEST_COURSE_NAME, "test_task")[1]
    updated_score = 80
    score = _update_score(group, task, updated_score, "", 0, datetime.now(tz=ZoneInfo("UTC")))
    assert score == updated_score


def test_update_score_with_old_score(app):
    group = app.storage_api.find_task(TEST_COURSE_NAME, "test_task")[0]
    task = app.storage_api.find_task(TEST_COURSE_NAME, "test_task")[1]
    updated_score = 70
    old_score = 80
    score = _update_score(group, task, updated_score, "", old_score, datetime.now(tz=ZoneInfo("UTC")))
    assert score == old_score  # Should keep higher old score


def test_report_score_missing_task(app):
    with app.test_request_context():
        data = {"user_id": str(TEST_USER_ID)}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().post(f"/api/{TEST_COURSE_NAME}/report", data=data, headers=headers)
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b"task" in response.data


def test_report_score_missing_user(app):
    with app.test_request_context():
        data = {"task": TEST_TASK_NAME}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().post(f"/api/{TEST_COURSE_NAME}/report", data=data, headers=headers)
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b"user_id" in response.data


def test_report_score_success(app):
    with app.test_request_context():
        data = {"task": TEST_TASK_NAME, "user_id": str(TEST_USER_ID), "score": "90", "check_deadline": "True"}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
        expected_data = {"username": TEST_USERNAME, "score": 90}

        response = app.test_client().post(f"/api/{TEST_COURSE_NAME}/report", data=data, headers=headers)
        assert response.status_code == HTTPStatus.OK
        data = json.loads(response.data)
        assert data["username"] == expected_data["username"]
        assert data["score"] == expected_data["score"]


def test_get_score_success(app):
    with app.test_request_context():
        data = {"task": TEST_TASK_NAME, "username": TEST_USERNAME}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
        expected_data = {"score": 80, "task": TEST_TASK_NAME, "user_id": TEST_USER_ID, "username": TEST_USERNAME}

        response = app.test_client().get(f"/api/{TEST_COURSE_NAME}/score", data=data, headers=headers)
        assert response.status_code == HTTPStatus.OK
        data = json.loads(response.data)
        assert data == expected_data


def test_update_database_not_json(app, authenticated_client, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    response = authenticated_client.post(
        f"/api/{TEST_COURSE_NAME}/database/update", data="not json", content_type="text/plain"
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Request must be JSON" in data["message"]


def test_update_database_missing_fields(app, authenticated_client):
    # Empty data
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json={})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Missing required fields" in data["message"]

    # Partial data
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json={"username": TEST_USERNAME})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Missing required fields" in data["message"]


def test_update_database_success(app, authenticated_client):
    test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=test_data)
    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)
    assert data["success"]


def test_update_database_invalid_score_type(app, authenticated_client):
    test_data = {
        "username": TEST_USERNAME,
        "scores": {
            "task1": "not a number",  # invalid score type
            "task2": 85,
        },
    }
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=test_data)
    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)
    assert data["success"]


def test_update_database_unauthorized(app, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
    response = app.test_client().post(f"/api/{TEST_COURSE_NAME}/database/update", json=test_data)
    # Signup
    assert response.status_code == HTTPStatus.FOUND
    assert response.location == f"http://localhost/api/{TEST_COURSE_NAME}/database/update"


def test_update_database_not_ready(app, authenticated_client):
    with patch.object(app.storage_api, "get_course") as mock_get_course:

        @dataclass
        class Course:
            is_ready = False

        mock_get_course.return_value = Course()

        test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
        response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=test_data)
        # Not ready
        assert response.status_code == HTTPStatus.FOUND


def test_requires_token_invalid_token(app):
    client = app.test_client()
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.post("/api/{TEST_COURSE_NAME}/report", headers=headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_requires_token_missing_token(app):
    client = app.test_client()
    response = client.post(f"/api/{TEST_COURSE_NAME}/report")
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_parse_flags_invalid_date(app):
    result = _parse_flags("flag:2024-13-45T25:99:99")  # Invalid date format
    assert result == timedelta()


def test_update_score_after_deadline(app):
    group = app.storage_api.find_task(TEST_COURSE_NAME, TEST_TASK_NAME)[0]
    task = app.storage_api.find_task(TEST_COURSE_NAME, TEST_TASK_NAME)[1]
    score = 100
    flags = ""
    old_score = 0
    submit_time = datetime.now(ZoneInfo("UTC"))

    # Test with check_deadline=True
    result = _update_score(group, task, score, flags, old_score, submit_time, check_deadline=True)
    assert result == score * group.get_current_percent_multiplier(submit_time)


def test_update_config_success(app):
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    data = {"test": "config"}
    response = client.post(f"/api/{TEST_COURSE_NAME}/update_config", data=yaml.dump(data), headers=headers)
    assert response.status_code == HTTPStatus.OK


def test_update_cache_success(app):
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    response = client.post(f"/api/{TEST_COURSE_NAME}/update_cache", headers=headers)
    assert response.status_code == HTTPStatus.OK


def test_get_database_unauthorized(app, mock_gitlab_oauth):
    app.debug = False  # Disable debug mode to test auth
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    response = client.get(f"/api/{TEST_COURSE_NAME}/database")
    assert response.status_code == HTTPStatus.FOUND  # Redirects to login


def test_get_database_not_ready(app, mock_gitlab_oauth):
    with patch.object(app.storage_api, "get_course") as mock_get_course:

        @dataclass
        class Course:
            is_ready = False

        mock_get_course.return_value = Course()
        app.debug = False  # Disable debug mode to test auth
        app.oauth = mock_gitlab_oauth
        client = app.test_client()
        with client.session_transaction() as session:
            session["gitlab"] = {
                "version": 1.5,
                "username": TEST_USERNAME,
                "user_id": TEST_USER_ID,
            }
        response = client.get(f"/api/{TEST_COURSE_NAME}/database")
        assert response.status_code == HTTPStatus.FOUND  # Redirects to not ready page


def test_update_database_invalid_json(app, authenticated_client, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
        }
    response = authenticated_client.post(
        f"/api/{TEST_COURSE_NAME}/database/update", data="invalid json", content_type="application/json"
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_update_database_missing_student(app, authenticated_client, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
        }
    data = {"scores": {TEST_TASK_NAME: 100}}
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=data)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Missing required fields" in json.loads(response.data)["message"]


def test_report_score_with_flags(app):
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    data = {
        "user_id": str(TEST_USER_ID),
        "task": TEST_TASK_NAME,
        "score": "100",  # API expects string
        "flags": "flag:2024-03-20T15:30:00",
        "submit_time": "2024-03-20T15:30:00",
        "check_deadline": "True",
    }
    response = client.post(f"/api/{TEST_COURSE_NAME}/report", data=data, headers=headers)  # Use form data, not JSON
    assert response.status_code == HTTPStatus.OK


def test_report_score_invalid_submit_time(app):
    with app.test_request_context():
        client = app.test_client()
        headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

        data = {
            "student": TEST_USERNAME,
            "task": TEST_TASK_NAME,
            "score": 100,
            "flags": "",
            "submit_time": "invalid_time",
        }
        response = client.post(f"/api/{TEST_COURSE_NAME}/report", json=data, headers=headers)
        assert response.status_code == HTTPStatus.BAD_REQUEST


def test_get_score_invalid_student(app):
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    response = client.get(
        f"/api/{TEST_COURSE_NAME}/score", data={"username": "nonexistent_user", "task": TEST_TASK_NAME}, headers=headers
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_database_invalid_task(app, authenticated_client, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
        }
    data = {"username": TEST_USERNAME, "scores": {INVALID_TASK_NAME: 100}}
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=data)
    # API silently ignores invalid tasks
    assert response.status_code == HTTPStatus.OK


def test_update_database_invalid_score_value(app, authenticated_client, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
        }
    data = {
        "username": TEST_USERNAME,
        "scores": {
            TEST_TASK_NAME: -1  # Invalid score value
        },
    }
    response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=data)
    # API silently ignores invalid scores
    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)
    assert data["success"]


def test_no_course_in_db(app):
    """Test the decorator when no course information is present in the database, leading to an abort."""

    app.storage_api = MagicMock(DataBaseApi)
    app.storage_api.get_course.return_value = None
    headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
    client = app.test_client()
    response = client.post(f"/api/{TEST_COURSE_NAME}/report", headers=headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_process_score_no_score():
    """Test when score is not in form_data"""
    form_data = {}
    task_score = 100
    assert _process_score(form_data, task_score) is None


def test_process_score_integer():
    """Test when score is an integer string"""
    score_integer = 75
    form_data = {"score": str(score_integer)}
    task_score = 100
    assert _process_score(form_data, task_score) == score_integer


def test_process_score_float_multiplier():
    """Test when score is a float multiplier"""
    score_float = 0.8
    form_data = {"score": str(score_float)}
    task_score = 100
    assert _process_score(form_data, task_score) == score_float * task_score


def test_process_score_zero():
    """Test when score is zero"""
    form_data = {"score": "0"}
    task_score = 100
    assert _process_score(form_data, task_score) == 0


def test_process_score_negative():
    """Test when score is negative"""
    form_data = {"score": "-0.5"}
    task_score = 100
    assert _process_score(form_data, task_score) == 0


def test_process_score_too_large():
    """Test when score is above max_score"""
    form_data = {"score": "2.5"}
    task_score = 100
    with pytest.raises(HTTPException) as exc_info:
        _process_score(form_data, task_score)
    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


def test_process_score_invalid_format():
    """Test when score is not a valid number"""
    form_data = {"score": "invalid"}
    task_score = 100
    with pytest.raises(HTTPException) as exc_info:
        _process_score(form_data, task_score)
    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


def test_get_student_by_username():
    """Test getting student by username"""
    mock_gitlab = MagicMock()
    test_student = Student(id=1, username="test_user", name="Test User")
    mock_gitlab.get_student_by_username.return_value = test_student

    result = _get_student(mock_gitlab, None, "test_user")
    assert result == test_student
    mock_gitlab.get_student_by_username.assert_called_once_with("test_user")


def test_get_student_by_id():
    """Test getting student by user_id"""
    mock_gitlab = MagicMock()
    test_student = Student(id=1, username="test_user", name="Test User")
    mock_gitlab.get_student.return_value = test_student

    result = _get_student(mock_gitlab, 1, None)
    assert result == test_student
    mock_gitlab.get_student.assert_called_once_with(1)


def test_get_student_no_id_or_username():
    """Test when neither user_id nor username is provided"""
    mock_gitlab = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        _get_student(mock_gitlab, None, None)
    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_get_student_username_not_found():
    """Test when username is not found"""
    mock_gitlab = MagicMock()
    mock_gitlab.get_student_by_username.side_effect = Exception("Student not found")

    with pytest.raises(HTTPException) as exc_info:
        _get_student(mock_gitlab, None, "nonexistent")
    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_get_student_id_not_found():
    """Test when user_id is not found"""
    mock_gitlab = MagicMock()
    mock_gitlab.get_student.side_effect = Exception("Student not found")

    with pytest.raises(HTTPException) as exc_info:
        _get_student(mock_gitlab, 999, None)
    assert exc_info.value.code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("task_name", [INVALID_TASK_NAME, TASK_NAME_WITH_DISABLED_TASK_OR_GROUP])
def test_post_requests_invalid_or_disabled_task(app, task_name):
    with app.test_request_context():
        data = {"task": task_name, "user_id": str(TEST_USER_ID)}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().post(f"/api/{TEST_COURSE_NAME}/report", data=data, headers=headers)
        assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("path", [f"/api/{TEST_COURSE_NAME}/score"])
@pytest.mark.parametrize("task_name", [INVALID_TASK_NAME, TASK_NAME_WITH_DISABLED_TASK_OR_GROUP])
def test_get_requests_invalid_or_disabled_task(app, path, task_name):
    with app.test_request_context():
        data = {"task": task_name, "user_id": str(TEST_USER_ID)}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().get(path, data=data, headers=headers)
        assert response.status_code == HTTPStatus.NOT_FOUND
