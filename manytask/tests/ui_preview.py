"""Disposable loopback fixture; never import from production.

Run: gunicorn 'tests.ui_preview:create_preview_app()' --bind 127.0.0.1:8082
Override MANYTASK_PREVIEW_DATABASE_URL for the image smoke.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import yaml
from flask import abort, redirect, session

# Importing the package loads main.py, so disable dotenv before the first import.
with patch("dotenv.load_dotenv", return_value=False):
    from manytask import main
    from manytask.abstract import AuthenticatedUser, RmsUser
    from manytask.course import CourseConfig, CourseStatus
    from manytask.mock_auth import MockAuthApi
    from manytask.mock_rms import MockRmsApi

ROLES = dict(
    zip(("student", "course_admin", "namespace_admin", "instance_admin"), (f"student{i:03}" for i in range(4)))
)
STUDENT_COUNT = 230


class SessionMockAuth(MockAuthApi):
    """Each request authenticates its seeded identity, with all real guards enabled."""

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        return AuthenticatedUser(id=session["auth"]["user_auth_id"], username=session["auth"]["username"])


def _seed(app, rms):
    storage = app.storage_api
    group_id = rms.create_namespace_group("Gravity Sandbox", "gravity")
    for index in range(STUDENT_COUNT):
        user = RmsUser(id=str(1000 + index), username=f"student{index:03}", name=f"Student {index}")
        rms.users[user.id] = user
        rms.users_by_username[user.username] = user
        rms.create_project(user, "sandbox/students", "sandbox/public")
    if storage.get_course("sandbox") is not None:
        for stored in storage.get_all_users():
            user = RmsUser(id=stored.rms_id, username=stored.username, name=stored.first_name)
            rms.users[user.id] = user
            rms.users_by_username[user.username] = user
        return
    for index in range(STUDENT_COUNT):
        storage.update_or_create_user(
            f"student{index:03}",
            "Иван" if index == 0 else "Student",
            "学生" if index == 0 else f"Example{index}",
            str(1000 + index),
            1000 + index,
        )
    storage.set_instance_admin_status(ROLES["instance_admin"], True)
    namespace = storage.create_namespace(
        "Gravity Sandbox", "gravity", "Disposable browser fixture", group_id, ROLES["namespace_admin"]
    )
    for name, status in (
        ("sandbox", CourseStatus.IN_PROGRESS),
        ("empty", CourseStatus.IN_PROGRESS),
        ("pending", CourseStatus.CREATED),
    ):
        storage.create_course(
            CourseConfig(
                course_name=name,
                namespace_id=namespace.id,
                gitlab_course_group=name,
                gitlab_course_public_repo=f"{name}/public",
                gitlab_course_students_group=f"{name}/students",
                gitlab_default_branch="main",
                registration_secret="preview",
                token=f"preview-{name}-token",
                show_allscores=True,
                status=status,
            )
        )
    config = yaml.safe_load((Path(__file__).resolve().parents[2] / "course-template/.manytask.yml").read_text())
    today = datetime.now(ZoneInfo("Europe/Moscow")).replace(hour=10, minute=0, second=0, microsecond=0)
    schedule = config["deadlines"]["schedule"]
    for index, group in enumerate(schedule):
        group["start"] = today - timedelta(days=35 - 7 * index)
        group["end"] = group["start"] + timedelta(days=60)
    schedule[1]["start"] = schedule[0]["start"]
    for index, name in enumerate(("__proto__", "10", "2")):
        schedule.append(
            {
                "group": name,
                "start": today - timedelta(days=index + 1),
                "end": today + timedelta(days=60),
                "enabled": True,
                "tasks": [{"task": "dotted.task" if index == 0 else f"edge{index}", "score": 100}],
            }
        )
    config["grades"] = {"grades": {5: [{"percent": 90}], 4: [{"percent": 75}], 3: [{"percent": 60}], 2: [{"": 0}]}}
    config["ui"]["task_url_template"] = "http://127.0.0.1:8082/__preview__/task/$GROUP_NAME/$TASK_NAME"
    config["ui"]["links"] = {"Role entry links": "/__preview__/"}
    app.store_config("sandbox", config)
    tasks = [task["task"] for group in schedule for task in group["tasks"]]
    for index in range(STUDENT_COUNT):
        username = f"student{index:03}"
        storage.sync_user_on_course("sandbox", username, course_admin=index == 1)
        for task_index, task in enumerate(tasks):
            score = 0 if index == 0 else -5 if index == 1 else (index * 7 + task_index * 11) % 101
            storage.store_score("sandbox", username, task, lambda _name, _old, value=score: value)
    storage.update_student_comment("sandbox", "student000", 'Unicode Иван, "quoted"\nsecond line')


def create_preview_app():
    os.environ.update(
        DATABASE_URL=os.environ.get(
            "MANYTASK_PREVIEW_DATABASE_URL",
            "postgresql://manytask_preview:manytask_preview@127.0.0.1:15433/manytask_gravity_browser",
        ),
        INITIAL_INSTANCE_ADMIN=ROLES["instance_admin"],
        APPLY_MIGRATIONS="true",
        FLASK_SECRET_KEY="disposable-gravity-browser-only",
        RMS="mock",
        FLASK_DEBUG="0",
        GITLAB_URL="http://127.0.0.1:8082",
    )
    # Do not load developer credentials. RMS stays mocked even for SourceCraft layout.
    logging = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "root": {"level": "WARNING", "handlers": ["console"]},
    }
    config = main.local_config.DebugLocalConfig(rms="mock", gitlab_url="http://127.0.0.1:8082")
    with (
        patch.object(main, "_logging_config", return_value=logging),
        patch.object(main.local_config.LocalConfig, "from_env", return_value=config),
    ):
        app = main.create_app(debug=False)
    app.debug = False
    app.config.update(SESSION_COOKIE_NAME="manytask_gravity_browser", SEND_FILE_MAX_AGE_DEFAULT=0)
    app.auth_api = SessionMockAuth()
    rms = app.rms_api
    assert isinstance(rms, MockRmsApi)
    _seed(app, rms)

    @app.before_request
    def select_mock_layout():
        app.app_config.rms = "sourcecraft" if session.get("preview_sourcecraft") else "mock"

    @app.get("/__preview__/")
    def entries():
        links = "".join(f'<li><a href="/__preview__/as/{role}">{role}</a></li>' for role in ROLES)
        return f"<h1>Disposable Gravity browser preview</h1><ul>{links}</ul><a href='/signup'>Signup</a>"

    @app.get("/__preview__/as/<role>")
    def identity(role):
        if role not in ROLES:
            abort(404)
        username = ROLES[role]
        user = app.storage_api.get_stored_user_by_username(username)
        session.clear()
        session["auth"] = {
            "username": username,
            "user_auth_id": user.auth_id,
            "version": 1.6,
            "access_token": "preview",
            "refresh_token": "preview",
        }
        session["rms"] = {"username": username, "rms_id": user.rms_id, "version": 1.1}
        session["manytask"] = {"username": username, "user_id": user.user_id, "version": 1.0}
        return redirect("/")

    @app.get("/__preview__/signup-finish/<username>")
    def finish_identity(username):
        if not username.startswith("browser") or not username.isalnum():
            abort(400)
        user_id = str(max(map(int, rms.users)) + 1)
        user = RmsUser(id=user_id, username=username, name="Browser User")
        rms.users[user_id] = user
        rms.users_by_username[username] = user
        session.clear()
        session["auth"] = {
            "username": username,
            "user_auth_id": int(user_id),
            "version": 1.6,
            "access_token": "preview",
            "refresh_token": "preview",
        }
        return redirect("/signup_finish")

    @app.get("/__preview__/sourcecraft")
    def sourcecraft_layout():
        session["preview_sourcecraft"] = True
        return redirect("/signup")

    @app.get("/__preview__/task/<group>/<task>")
    def task_readme(group, task):
        return f"Preview task: {group}/{task}", {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/__preview__/health")
    def preview_health():
        return {"debug": app.debug, "students": STUDENT_COUNT, "database": "manytask_gravity_browser"}

    return app
