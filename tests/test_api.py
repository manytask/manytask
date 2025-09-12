import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Callable
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import yaml
from dotenv import load_dotenv
from flask import Flask, json, url_for
from pytest import approx
from werkzeug.exceptions import HTTPException

from manytask.abstract import AuthenticatedUser, RmsUser, StoredUser
from manytask.api import _parse_flags, _process_score, _update_score, _validate_and_extract_params
from manytask.api import bp as api_bp
from manytask.config import ManytaskDeadlinesType, ManytaskGroupConfig, ManytaskTaskConfig
from manytask.course import CourseStatus
from manytask.database import DataBaseApi, TaskDisabledError
from manytask.glab import GitLabApiException
from manytask.web import course_bp, root_bp
from tests.constants import (
    INVALID_TASK_NAME,
    TASK_NAME_WITH_DISABLED_TASK_OR_GROUP,
    TEST_COURSE_NAME,
    TEST_FIRST_NAME,
    TEST_INVALID_USER_ID,
    TEST_INVALID_USERNAME,
    TEST_LAST_NAME,
    TEST_NAME,
    TEST_RMS_ID,
    TEST_SECRET_KEY,
    TEST_TASK_GROUP_NAME,
    TEST_TASK_NAME,
    TEST_USER_ID,
    TEST_USERNAME,
)


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    load_dotenv()
    if not os.getenv("MANYTASK_COURSE_TOKEN"):
        monkeypatch.setenv("MANYTASK_COURSE_TOKEN", "test_token")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_key")
    monkeypatch.setenv("TESTING", "true")
    yield


@pytest.fixture
def app(mock_storage_api, mock_rms_api, mock_auth_api):
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = TEST_SECRET_KEY
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    app.storage_api = mock_storage_api
    app.rms_api = mock_rms_api
    app.auth_api = mock_auth_api
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
            self.name = TEST_TASK_GROUP_NAME
            self.tasks = [mock_task]

        @staticmethod
        def get_current_percent_multiplier(now, deadlines_type):
            return 1.0

        def get_tasks(self):
            return self.tasks

    return MockGroup()


@pytest.fixture
def mock_rms_user():
    class MockRmsUser:
        def __init__(self, user_id, username, name):
            self.id = user_id
            self.username = username
            self.name = name

    return MockRmsUser


@pytest.fixture
def mock_storage_api(mock_course, mock_task, mock_group):  # noqa: C901
    class MockStorageApi:
        def __init__(self):
            self.scores = {}
            self.stored_user = StoredUser(
                username=TEST_USERNAME,
                first_name=TEST_FIRST_NAME,
                last_name=TEST_LAST_NAME,
                rms_id=TEST_RMS_ID,
                instance_admin=False,
            )
            self.course_name = TEST_COURSE_NAME
            self.course_admin = False

        def store_score(self, _course_name, username, task_name, update_fn):
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

        def check_if_course_admin(self, _course_name, _username):
            return True

        def update_cached_scores(self, _course_name):
            pass

        def sync_columns(self, _course_name, _deadlines):
            pass

        def update_task_groups_from_config(self, _course_name, _config_data):
            pass

        def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool:
            self.course_admin = course_admin
            return course_admin

        def check_user_on_course(self, *a, **k):
            return True

        @staticmethod
        def find_task(_course_name, task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            if task_name == TASK_NAME_WITH_DISABLED_TASK_OR_GROUP:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            return mock_course, mock_group, mock_task

        @staticmethod
        def get_now_with_timezone(_course_name):
            return datetime.now(tz=ZoneInfo("UTC"))

        def get_groups(self, _course_name):
            return [mock_group]

    return MockStorageApi()


@pytest.fixture
def mock_rms_api(mock_rms_user):
    class MockRmsApi:
        def __init__(self):
            self.course_admin = False
            self._rms_user_class = mock_rms_user

        def get_rms_user_by_id(self, user_id: int):
            if user_id == TEST_USER_ID:
                return self._rms_user_class(TEST_USER_ID, TEST_USERNAME, TEST_NAME)
            raise GitLabApiException("User not found")

        def get_rms_user_by_username(self, username):
            if username == TEST_USERNAME:
                return self._rms_user_class(TEST_USER_ID, TEST_USERNAME, TEST_NAME)
            raise GitLabApiException("User not found")

        def check_user_authenticated_in_rms(self, oauth, oauth_access_token, oauth_refresh_token):
            return True

        def get_authenticated_rms_user(self, access_token):
            return RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        @staticmethod
        def get_url_for_repo(username, course_students_group):
            return f"https://gitlab.com/{username}/test-repo"

        @staticmethod
        def check_project_exists(_project_name, _project_group):
            return True

    return MockRmsApi()


@pytest.fixture
def mock_auth_api():
    class MockAuthApi:
        def check_user_is_authenticated(
            self,
            oauth,
            oauth_access_token: str,
            oauth_refresh_token: str,
        ) -> bool:
            return True

        def get_authenticated_user(self, access_token):
            return AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)

    return MockAuthApi()


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.course_name = TEST_COURSE_NAME
            self.status = CourseStatus.IN_PROGRESS
            self.show_allscores = True
            self.registration_secret = "test_secret"
            self.token = os.environ["MANYTASK_COURSE_TOKEN"]
            self.gitlab_course_group = "test_group"
            self.gitlab_course_public_repo = "public_2025_spring"
            self.gitlab_course_students_group = "students_2025_spring"
            self.gitlab_default_branch = "main"
            self.deadlines_type = ManytaskDeadlinesType.HARD

    return MockCourse()


@pytest.fixture
def authenticated_client(app, mock_gitlab_oauth):
    """
    Provides a client with anauthenticated session
    """
    with (
        app.test_client() as client,
        patch.object(app.rms_api, "get_authenticated_rms_user") as mock_get_authenticated_rms_user,
        patch.object(app.rms_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
    ):
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_rms_user.return_value = RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name="")
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
            session["profile"] = {
                "version": 1.0,
                "username": TEST_USERNAME,
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
    course, group, task = app.storage_api.find_task(TEST_COURSE_NAME, "test_task")
    updated_score = 80
    score = _update_score(course, group, task, updated_score, "", 0, datetime.now(tz=ZoneInfo("UTC")))
    assert score == updated_score


def test_update_score_with_old_score(app):
    course, group, task = app.storage_api.find_task(TEST_COURSE_NAME, "test_task")
    updated_score = 70
    old_score = 80
    score = _update_score(course, group, task, updated_score, "", old_score, datetime.now(tz=ZoneInfo("UTC")))
    assert score == old_score  # Should keep higher old score


def create_percent_multiplier_calculator(
    start: datetime,
    duration: timedelta,
    steps: dict[float, datetime | timedelta],
    deadlines_type: ManytaskDeadlinesType,
) -> Callable:
    group = ManytaskGroupConfig(
        group="test",
        enabled=True,
        start=start,
        end=start + duration,
        steps={
            1.0: timedelta(days=2),
            0.5: start + timedelta(days=4),
            0.25: start + timedelta(days=8),
        },
        tasks=[
            ManytaskTaskConfig(
                task=TEST_TASK_NAME,
                score=100,
            )
        ],
    )

    def get_percent_multiplier(**kwargs) -> float:
        return group.get_current_percent_multiplier(start + timedelta(**kwargs), deadlines_type)

    return get_percent_multiplier


def test_interpolated_scores(mock_task):
    start = datetime(2025, 9, 1)
    get_percent_multiplier = create_percent_multiplier_calculator(
        start=start,
        duration=timedelta(days=10),
        steps={
            1.0: timedelta(days=2),
            0.5: start + timedelta(days=4),
            0.25: start + timedelta(days=8),
        },
        deadlines_type=ManytaskDeadlinesType.INTERPOLATE,
    )

    assert get_percent_multiplier(days=0) == approx(1.0)
    assert get_percent_multiplier(days=1) == approx(1.0)
    assert get_percent_multiplier(days=2) == approx(1.0)
    assert get_percent_multiplier(days=2, hours=9, minutes=36) == approx(0.9)
    assert get_percent_multiplier(days=3) == approx(0.75)
    assert get_percent_multiplier(days=4) == approx(0.5)
    assert get_percent_multiplier(days=5) == approx(0.4375)
    assert get_percent_multiplier(days=6) == approx(0.375)
    assert get_percent_multiplier(days=7) == approx(0.3125)
    assert get_percent_multiplier(days=8) == approx(0.25)
    assert get_percent_multiplier(days=9) == approx(0.25)
    assert get_percent_multiplier(days=9, hours=23, minutes=59, seconds=59) == approx(0.25)
    assert get_percent_multiplier(days=10, seconds=1) == approx(0)


def test_hard_scores(mock_task):
    start = datetime(2025, 9, 1)
    get_percent_multiplier = create_percent_multiplier_calculator(
        start=start,
        duration=timedelta(days=10),
        steps={
            1.0: timedelta(days=2),
            0.5: start + timedelta(days=4),
            0.25: start + timedelta(days=8),
        },
        deadlines_type=ManytaskDeadlinesType.HARD,
    )

    assert get_percent_multiplier(days=0) == approx(1.0)
    assert get_percent_multiplier(days=1) == approx(1.0)
    assert get_percent_multiplier(days=2) == approx(1.0)
    assert get_percent_multiplier(days=3) == approx(1.0)
    assert get_percent_multiplier(days=3, hours=23, minutes=59, seconds=59) == approx(1.0)
    assert get_percent_multiplier(days=4, seconds=1) == approx(0.5)
    assert get_percent_multiplier(days=5) == approx(0.5)
    assert get_percent_multiplier(days=6) == approx(0.5)
    assert get_percent_multiplier(days=7) == approx(0.5)
    assert get_percent_multiplier(days=7, hours=23, minutes=59, seconds=59) == approx(0.5)
    assert get_percent_multiplier(days=8, seconds=1) == approx(0.25)
    assert get_percent_multiplier(days=9) == approx(0.25)
    assert get_percent_multiplier(days=9, hours=23, minutes=59, seconds=59) == approx(0.25)
    assert get_percent_multiplier(days=10, seconds=1) == approx(0)


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
        data = {
            "task": TEST_TASK_NAME,
            "user_id": str(TEST_USER_ID),
            "score": "90",
            "check_deadline": "True",
        }
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
        expected_data = {
            "score": 80,
            "task": TEST_TASK_NAME,
            "user_id": TEST_USER_ID,
            "username": TEST_USERNAME,
        }

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
    with app.test_request_context():
        app.oauth = mock_gitlab_oauth
        test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
        response = app.test_client().post(f"/api/{TEST_COURSE_NAME}/database/update", json=test_data)
        # Signup
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.signup")


def test_update_database_not_ready(app, authenticated_client):
    with patch.object(app.storage_api, "get_course") as mock_get_course:

        @dataclass
        class Course:
            status = CourseStatus.CREATED

        mock_get_course.return_value = Course()

        test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
        response = authenticated_client.post(f"/api/{TEST_COURSE_NAME}/database/update", json=test_data)
        # Not ready
        assert response.status_code == HTTPStatus.FOUND


def test_requires_token_invalid_token(app):
    client = app.test_client()
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.post(f"/api/{TEST_COURSE_NAME}/report", headers=headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_requires_token_missing_token(app):
    client = app.test_client()
    response = client.post(f"/api/{TEST_COURSE_NAME}/report")
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_parse_flags_invalid_date(app):
    result = _parse_flags("flag:2024-13-45T25:99:99")  # Invalid date format
    assert result == timedelta()


def test_update_score_after_deadline(app):
    course, group, task = app.storage_api.find_task(TEST_COURSE_NAME, TEST_TASK_NAME)
    score = 100
    flags = ""
    old_score = 0
    submit_time = datetime.now(ZoneInfo("UTC"))

    # Test with check_deadline=True
    result = _update_score(course, group, task, score, flags, old_score, submit_time, check_deadline=True)
    assert result == score * group.get_current_percent_multiplier(submit_time, course.deadlines_type)


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
            status = CourseStatus.CREATED

        mock_get_course.return_value = Course()
        app.debug = False  # Disable debug mode to test auth
        app.oauth = mock_gitlab_oauth
        client = app.test_client()
        with client.session_transaction() as session:
            session["gitlab"] = {
                "version": 1.5,
                "username": TEST_USERNAME,
                "user_id": TEST_USER_ID,
                "access_token": "123",
                "refresh_token": "123",
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
        f"/api/{TEST_COURSE_NAME}/score",
        data={"username": "nonexistent_user", "task": TEST_TASK_NAME},
        headers=headers,
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


def test_validate_and_extract_params_get_student_by_id(app):
    """Test parsing form data getting student by username"""
    form_data = {"user_id": TEST_USER_ID, "task": TEST_TASK_NAME}
    course_name = "Pyhton"

    rms_user, _, task, group = _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert rms_user.id == TEST_USER_ID
    assert rms_user.username == TEST_USERNAME
    assert rms_user.name == TEST_NAME
    assert task.name == TEST_TASK_NAME
    assert group.name == TEST_TASK_GROUP_NAME


def test_validate_and_extract_params_get_student_by_username(app):
    """Test parsing form data getting student by id"""
    form_data = {"username": TEST_USERNAME, "task": TEST_TASK_NAME}
    course_name = "Pyhton"

    rms_user, _, task, group = _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert rms_user.id == TEST_USER_ID
    assert rms_user.username == TEST_USERNAME
    assert rms_user.name == TEST_NAME
    assert task.name == TEST_TASK_NAME
    assert group.name == TEST_TASK_GROUP_NAME


def test_validate_and_extract_params_no_student_name_or_id(app):
    """Test parsing form data user is not defined"""
    form_data = {"task": TEST_TASK_NAME}
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


def test_validate_and_extract_params_both_student_name_and_id(app):
    """Test parsing form data user is not defined"""
    form_data = {
        "user_id": TEST_USER_ID,
        "username": TEST_USERNAME,
        "task": TEST_TASK_NAME,
    }
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


def test_validate_and_extract_params_user_id_not_an_int(app):
    """Test parsing form data user is not defined"""
    form_data = {"user_id": TEST_USERNAME, "task": TEST_TASK_NAME}
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


def test_validate_and_extract_params_no_task_name(app):
    """Test parsing form data when task is not defined"""
    form_data = {"username": TEST_USERNAME}
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


def test_validate_and_extract_params_student_id_not_found(app):
    """Test parsing form data wrong id"""
    form_data = {"user_id": TEST_INVALID_USER_ID, "task": TEST_TASK_NAME}
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_validate_and_extract_params_student_username_not_found(app):
    """Test parsing form data wrong username"""
    form_data = {"username": TEST_INVALID_USERNAME, "task": TEST_TASK_NAME}
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


def test_validate_and_extract_params_task_not_found(app):
    """Test parsing form data wrong task name"""
    form_data = {"user_id": TEST_USER_ID, "task": INVALID_TASK_NAME}
    course_name = "Pyhton"

    with pytest.raises(HTTPException) as exc_info:
        _validate_and_extract_params(form_data, app.rms_api, app.storage_api, course_name)

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
