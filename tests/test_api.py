import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import yaml
from dotenv import load_dotenv
from flask import Flask, Response, json, url_for

from manytask.abstract import StoredUser
from manytask.api import _parse_flags, _update_score
from manytask.api import bp as api_bp
from manytask.database import DataBaseApi
from manytask.glab import Student
from manytask.web import bp as web_bp

# Constants
TEST_USER_ID = 123
TEST_USERNAME = "test_user"
INVALID_TASK_NAME = "invalid_task"
TEST_TASK_NAME = "test_task"
TEST_SECRET_KEY = "test_key"
TEST_COURSE_NAME = "Test Course"


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    load_dotenv()
    if not os.getenv("MANYTASK_COURSE_TOKEN"):
        monkeypatch.setenv("MANYTASK_COURSE_TOKEN", "test_token")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_key")
    monkeypatch.setenv("TESTING", "true")
    yield


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = TEST_SECRET_KEY
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    return app


@pytest.fixture
def mock_course():
    class MockGroup:
        def __init__(self):
            self.tasks = []

        @staticmethod
        def get_current_percent_multiplier(now):
            return 1.0

        def get_tasks(self):
            return self.tasks

    class MockTask:
        def __init__(self):
            self.name = TEST_TASK_NAME
            self.score = 100

    class MockStudent:
        def __init__(self, student_id, username):
            self.id = student_id
            self.username = username

    class MockSolutionsApi:
        def store_task_from_folder(self, task_name, username, folder_path):
            pass

        def get_task_aggregated_zip_io(self, task_name):
            from io import BytesIO

            return BytesIO(b"test data")

    class MockDeadlines:
        def __init__(self):
            self.timezone = "UTC"
            self.mock_task = MockTask()
            self.mock_group = MockGroup()
            self.mock_group.tasks = [self.mock_task]
            self.groups = [self.mock_group]

        @staticmethod
        def get_now_with_timezone():
            return datetime.now(tz=ZoneInfo("UTC"))

        @staticmethod
        def find_task(task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            return MockGroup(), MockTask()

    class MockCourse:
        def __init__(self):
            self.config = {"test": "config"}
            self.deadlines = MockDeadlines()
            self.storage_api = self.storage_api()
            self.solutions_api = MockSolutionsApi()
            self.gitlab_api = self.gitlab_api()
            self.debug = False

        def store_config(self, config_data):
            self.config = config_data

        class storage_api:
            def __init__(self):
                self.scores = {}
                self.stored_user = StoredUser(username=TEST_USERNAME, course_admin=False)
                self.course_name = TEST_COURSE_NAME

            def store_score(self, student, task_name, update_fn):
                old_score = self.scores.get(f"{student.username}_{task_name}", 0)
                new_score = update_fn("", old_score)
                self.scores[f"{student.username}_{task_name}"] = new_score
                return new_score

            @staticmethod
            def get_scores(_username):
                return {"task1": 100, "task2": 90, "test_task": 80}

            @staticmethod
            def get_course(_name):
                @dataclass
                class Course:
                    token: str

                return Course(os.getenv("MANYTASK_COURSE_TOKEN"))

            def get_all_scores(self):
                return {"test_user": self.get_scores("test_user")}

            @staticmethod
            def get_stored_user(student):
                from manytask.abstract import StoredUser

                return StoredUser(username=student.username, course_admin=True)

            def update_cached_scores(self):
                pass

            def get_solutions(self, student):
                if student == TEST_USERNAME:
                    return {"solutions": []}
                raise Exception("Student not found")

            def sync_columns(self, deadlines):
                pass

            def update_task_groups_from_config(self, config_data):
                pass

            def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool:
                self.stored_user.course_admin = (
                    student.course_admin
                    if self.stored_user.course_admin != student.course_admin and student.course_admin
                    else self.stored_user.course_admin
                )
                return self.stored_user.course_admin

            def check_user_on_course(self, *a, **k):
                return True

        def get_groups(self):
            return self.groups

        class gitlab_api:
            def __init__(self):
                self.course_admin = False

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

            def get_authenticated_student(self, _gitlab_access_token):
                return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=self.course_admin)

            @staticmethod
            def check_project_exists(_student):
                return True

            @staticmethod
            def _parse_user_to_student(user: dict[str, Any]):
                return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

    return MockCourse()


@pytest.fixture
def mock_gitlab_oauth():
    class MockGitlabOauth:
        class gitlab:
            @staticmethod
            def authorize_access_token():
                return {"access_token": "", "refresh_token": ""}

            @staticmethod
            def authorize_redirect(redirect_uri: str):
                resp = Response(status=302)
                resp.location = url_for("web.login")
                return resp

    return MockGitlabOauth()


@pytest.fixture
def authenticated_client(app, mock_course, mock_gitlab_oauth):
    """
    Provides a client with anauthenticated session
    """
    with (
        app.test_client() as client,
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.gitlab_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_student.return_value = Student(
            id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=False
        )
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
                "repo": "test_repo",
                "course_admin": False,
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
        response = app.test_client().get("/api/healthcheck")
        assert response.status_code == 200
        assert response.data == b"OK"


def test_report_score_missing_task(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {"user_id": str(TEST_USER_ID)}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().post("/api/report", data=data, headers=headers)
        assert response.status_code == 400
        assert b"task" in response.data


def test_report_score_missing_user(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {"task": TEST_TASK_NAME}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().post("/api/report", data=data, headers=headers)
        assert response.status_code == 400
        assert b"user_id" in response.data


def test_report_score_invalid_task(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {"task": INVALID_TASK_NAME, "user_id": str(TEST_USER_ID)}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}

        response = app.test_client().post("/api/report", data=data, headers=headers)
        assert response.status_code == 404


def test_report_score_success(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {"task": TEST_TASK_NAME, "user_id": str(TEST_USER_ID), "score": "90", "check_deadline": "True"}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
        expected_data = {"username": TEST_USERNAME, "score": 90}

        response = app.test_client().post("/api/report", data=data, headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["username"] == expected_data["username"]
        assert data["score"] == expected_data["score"]


def test_get_score_success(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        data = {"task": TEST_TASK_NAME, "username": TEST_USERNAME}
        headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
        expected_data = {"score": 80, "task": TEST_TASK_NAME, "user_id": TEST_USER_ID, "username": TEST_USERNAME}

        response = app.test_client().get("/api/score", data=data, headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == expected_data


def test_update_database_not_json(app, mock_course, authenticated_client, mock_gitlab_oauth):
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    response = authenticated_client.post("/api/database/update", data="not json", content_type="text/plain")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Request must be JSON" in data["message"]


def test_update_database_missing_fields(app, mock_course, authenticated_client):
    app.course = mock_course

    # Empty data
    response = authenticated_client.post("/api/database/update", json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Missing required fields" in data["message"]

    # Partial data
    response = authenticated_client.post("/api/database/update", json={"username": TEST_USERNAME})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["success"] is False
    assert "Missing required fields" in data["message"]


def test_update_database_success(app, mock_course, authenticated_client):
    app.course = mock_course
    test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
    response = authenticated_client.post("/api/database/update", json=test_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"]


def test_update_database_invalid_score_type(app, mock_course, authenticated_client):
    app.course = mock_course
    test_data = {
        "username": TEST_USERNAME,
        "scores": {
            "task1": "not a number",  # invalid score type
            "task2": 85,
        },
    }
    response = authenticated_client.post("/api/database/update", json=test_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"]


def test_update_database_unauthorized(app, mock_course, mock_gitlab_oauth):
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
    response = app.test_client().post("/api/database/update", json=test_data)
    # Signup
    assert response.status_code == 302
    assert response.location == "/login"


def test_update_database_not_ready(app, mock_course, authenticated_client):
    mock_course.config = None
    app.course = mock_course
    test_data = {"username": TEST_USERNAME, "scores": {"task1": 90, "task2": 85}}
    response = authenticated_client.post("/api/database/update", json=test_data)
    # Not ready
    assert response.status_code == 302


def test_requires_token_invalid_token(app, mock_course):
    client = app.test_client()
    app.course = mock_course
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.post("/api/report", headers=headers)
    assert response.status_code == 403


def test_requires_token_missing_token(app, mock_course):
    client = app.test_client()
    app.course = mock_course
    response = client.post("/api/report")
    assert response.status_code == 403


def test_parse_flags_invalid_date(app):
    result = _parse_flags("flag:2024-13-45T25:99:99")  # Invalid date format
    assert result == timedelta()


def test_update_score_after_deadline(mock_course):
    group = mock_course.deadlines.find_task(TEST_TASK_NAME)[0]
    task = mock_course.deadlines.find_task(TEST_TASK_NAME)[1]
    score = 100
    flags = ""
    old_score = 0
    submit_time = datetime.now(ZoneInfo("UTC"))

    # Test with check_deadline=True
    result = _update_score(group, task, score, flags, old_score, submit_time, check_deadline=True)
    assert result == score * group.get_current_percent_multiplier(submit_time)


def test_get_solutions_success(app, mock_course):
    app.course = mock_course
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    response = client.get("/api/solutions", data={"task": TEST_TASK_NAME}, headers=headers)
    assert response.status_code == 200


def test_get_solutions_missing_student(app, mock_course):
    app.course = mock_course
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    response = client.get("/api/solutions", headers=headers)
    assert response.status_code == 400


def test_update_config_success(app, mock_course):
    app.course = mock_course
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    data = {"test": "config"}
    response = client.post("/api/update_config", data=yaml.dump(data), headers=headers)
    assert response.status_code == 200


def test_update_cache_success(app, mock_course):
    app.course = mock_course
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    response = client.post("/api/update_cache", headers=headers)
    assert response.status_code == 200


def test_get_database_unauthorized(app, mock_course, mock_gitlab_oauth):
    app.debug = False  # Disable debug mode to test auth
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    response = client.get("/api/database")
    assert response.status_code == 302  # Redirects to login


def test_get_database_not_ready(app, mock_course, mock_gitlab_oauth):
    app.debug = False  # Disable debug mode to test auth
    mock_course.config = None
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
            "repo": "test-repo",
            "course_admin": True,
        }
    response = client.get("/api/database")
    assert response.status_code == 302  # Redirects to not ready page


def test_update_database_invalid_json(app, authenticated_client, mock_course, mock_gitlab_oauth):
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
            "repo": "test-repo",
            "course_admin": True,
        }
    response = authenticated_client.post("/api/database/update", data="invalid json", content_type="application/json")
    assert response.status_code == 400


def test_update_database_missing_student(app, authenticated_client, mock_course, mock_gitlab_oauth):
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
            "repo": "test-repo",
            "course_admin": True,
        }
    data = {"scores": {TEST_TASK_NAME: 100}}
    response = authenticated_client.post("/api/database/update", json=data)
    assert response.status_code == 400
    assert "Missing required fields" in json.loads(response.data)["message"]


def test_report_score_with_flags(app, mock_course):
    app.course = mock_course
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
    response = client.post("/api/report", data=data, headers=headers)  # Use form data, not JSON
    assert response.status_code == 200


def test_report_score_invalid_submit_time(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        client = app.test_client()
        headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

        data = {
            "student": TEST_USERNAME,
            "task": TEST_TASK_NAME,
            "score": 100,
            "flags": "",
            "submit_time": "invalid_time",
        }
        response = client.post("/api/report", json=data, headers=headers)
        assert response.status_code == 400


def test_get_score_invalid_student(app, mock_course):
    app.course = mock_course
    client = app.test_client()
    headers = {"Authorization": f"Bearer {os.getenv('MANYTASK_COURSE_TOKEN')}"}

    response = client.get("/api/score", data={"username": "nonexistent_user", "task": TEST_TASK_NAME}, headers=headers)
    assert response.status_code == 404


def test_update_database_invalid_task(app, authenticated_client, mock_course, mock_gitlab_oauth):
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
            "repo": "test-repo",
            "course_admin": True,
        }
    data = {"username": TEST_USERNAME, "scores": {INVALID_TASK_NAME: 100}}
    response = authenticated_client.post("/api/database/update", json=data)
    # API silently ignores invalid tasks
    assert response.status_code == 200


def test_update_database_invalid_score_value(app, authenticated_client, mock_course, mock_gitlab_oauth):
    app.course = mock_course
    app.oauth = mock_gitlab_oauth
    client = app.test_client()
    with client.session_transaction() as session:
        session["gitlab"] = {
            "version": 1.5,
            "username": TEST_USERNAME,
            "user_id": TEST_USER_ID,
            "repo": "test-repo",
            "course_admin": True,
        }
    data = {
        "username": TEST_USERNAME,
        "scores": {
            TEST_TASK_NAME: -1  # Invalid score value
        },
    }
    response = authenticated_client.post("/api/database/update", json=data)
    # API silently ignores invalid scores
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"]


def test_no_course_in_db(app, mock_course):
    """Test the decorator when no course information is present in the database, leading to an abort."""

    app.course = mock_course
    app.course.storage_api = MagicMock(DataBaseApi)
    app.course.storage_api.course_name = "NoSuchCourse"
    app.course.storage_api.get_course.return_value = None
    headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
    client = app.test_client()
    response = client.post("/api/report", headers=headers)
    assert response.status_code == 403


def test_token_when_no_course(app):
    """Test the decorator when no course information is present in the database, leading to an abort."""

    headers = {"Authorization": f"Bearer {os.environ['MANYTASK_COURSE_TOKEN']}"}
    client = app.test_client()
    response = client.post("/api/report", headers=headers)
    assert response.status_code == 403
