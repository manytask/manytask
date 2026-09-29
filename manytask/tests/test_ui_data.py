"""Explicit data contracts for the migrated assignment page."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from flask import Flask

from manytask.config import ManytaskGroupConfig, ManytaskTaskConfig
from manytask.course import ManytaskDeadlinesType
from manytask.web import course_bp, instance_admin_bp, root_bp

EXPECTED_EARNED = 17
EXPECTED_MAXIMUM = 13
EXPECTED_PROGRESS = 87


def _context(deadlines_type=ManytaskDeadlinesType.HARD):
    tz = ZoneInfo("Europe/Moscow")
    group = ManytaskGroupConfig(
        group="__proto__</script>",
        start=datetime(2026, 1, 1, tzinfo=tz),
        steps={
            0.75: datetime(2026, 1, 2, 12, tzinfo=tz),
            0.5: datetime(2026, 1, 3, 12, tzinfo=tz),
        },
        end=timedelta(days=5),
        tasks=[
            ManytaskTaskConfig(task="10", score=10),
            ManytaskTaskConfig(task="2", score=5, is_bonus=True, url="https://sourcecraft.dev/task/2"),
            ManytaskTaskConfig(task="special", score=3, is_special=True),
        ],
    )
    storage = SimpleNamespace(get_groups=lambda *args, **kwargs: [group])
    return {
        "app": SimpleNamespace(storage_api=storage),
        "course_name": "a.b",
        "username": "Алиса",
        "now": datetime(2026, 1, 3, 9, tzinfo=tz),
        "scores": {"10": 12, "2": 2, "special": 3},
        "task_stats": {"10": 0.25, "2": 0.5},
        "task_url_template": "https://sourcecraft.dev/$USER_NAME/$GROUP_NAME/$TASK_NAME",
        "task_url_username": "alice-normalized",
        "deadlines_type": deadlines_type,
        "sourcecraft_accept_invite_required": True,
    }


def test_assignments_data_preserves_server_deadlines_scores_and_provider_links():
    from manytask.ui_assignments import serialize

    context = _context()
    data = serialize(context)
    group = data["groups"][0]
    assert data["courseName"] == "a.b"
    assert data["sourcecraftInviteUrl"] == "https://sourcecraft.dev/me/organizations"
    assert group["name"] == "__proto__</script>"
    assert group["end"] == "2026-01-06T00:00:00+03:00"
    assert group["earned"] == EXPECTED_EARNED
    assert group["maximum"] == EXPECTED_MAXIMUM
    assert [task["state"] for task in group["tasks"]] == ["over_solved", "partial", "solved"]
    assert [task["url"] for task in group["tasks"]] == [
        "https://sourcecraft.dev/alice-normalized/__proto__</script>/10",
        "https://sourcecraft.dev/task/2",
        "https://sourcecraft.dev/alice-normalized/__proto__</script>/special",
    ]
    assert [item["statistics"] for item in group["tasks"]] == [0.25, 0.5, 0]
    assert [deadline["passed"] for deadline in group["deadlines"]] == [True, False, False]
    assert [deadline["urgent"] for deadline in group["deadlines"]] == [False, True, False]
    assert [deadline["percent"] for deadline in group["deadlines"]] == [1.0, 0.75, 0.5]
    assert group["deadlines"][1]["remaining"] == "Deadline expires in: 3 h."
    assert group["deadlines"][1]["progress"] == EXPECTED_PROGRESS
    assert group["deadlines"][1]["tz"] == "MSK"
    assert group["graph"] is None


def test_assignments_graph_is_exact_model_output_and_empty_course_is_safe():
    from manytask.ui_assignments import serialize

    context = _context(ManytaskDeadlinesType.INTERPOLATE)
    group = context["app"].storage_api.get_groups()[0]
    data = serialize(context)
    assert data["groups"][0]["graph"] == group.get_graph_data(context["now"], ManytaskDeadlinesType.INTERPOLATE)
    context["app"].storage_api.get_groups = lambda *args, **kwargs: []
    assert serialize(context)["groups"] == []


def test_shared_course_navigation_uses_authorized_route_context():
    from manytask.ui_shared import serialize_shared

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(instance_admin_bp)
    app.app_config = SimpleNamespace(rms="sourcecraft")
    with app.test_request_context("/a.b/"):
        shared = serialize_shared(
            {
                "course_name": "a.b",
                "username": "alice",
                "scores": {"one": 8},
                "bonus_score": 2,
                "max_started_score": 10,
                "course_status": "in_progress",
                "courses": [{"name": "a.b", "url": "/a.b/"}],
                "student_repo_url": "https://repo",
                "student_ci_url": "https://ci",
                "show_allscores": True,
            }
        )
    assert shared["courses"] == [{"label": "a.b", "href": "/a.b/"}]
    assert shared["course"] == {
        "name": "a.b",
        "status": "in_progress",
        "score": 8,
        "bonusScore": 2,
        "maxStartedScore": 10,
    }
    assert [link["label"] for link in shared["navigation"]] == [
        "Courses",
        "Assignments",
        "My Repo",
        "My Submits",
        "All Scores",
    ]


def test_shared_navigation_includes_admin_course_links_only_for_authorized_role():
    from manytask.ui_shared import serialize_shared

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(instance_admin_bp)
    app.app_config = SimpleNamespace(rms="gitlab")
    with app.test_request_context("/a.b/"):
        shared = serialize_shared(
            {
                "app": app,
                "course_name": "a.b",
                "username": "admin",
                "scores": {},
                "show_allscores": False,
                "has_role": lambda _username, roles, _app, _course: "namespace_admin" in roles,
            }
        )
    assert [link["label"] for link in shared["navigation"]] == [
        "Courses",
        "Assignments",
        "All Scores",
        "Edit Course",
    ]


def test_shared_navigation_includes_instance_admin_panel_from_course_context():
    from manytask.ui_shared import serialize_shared

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(instance_admin_bp)
    app.app_config = SimpleNamespace(rms="gitlab")
    with app.test_request_context("/a.b/"):
        shared = serialize_shared(
            {
                "app": app,
                "course_name": "a.b",
                "username": "admin",
                "scores": {},
                "has_role": lambda _username, roles, _app, _course: "instance_admin" in roles,
            }
        )
    assert [link["label"] for link in shared["navigation"]] == [
        "Courses",
        "Assignments",
        "All Scores",
        "Edit Course",
        "Instance Admin panel",
    ]
    assert shared["capabilities"]["instanceAdmin"] is True
    assert shared["capabilities"]["namespaceAdmin"] is False


def test_grades_serializer_contains_only_routes_and_authorized_capabilities():
    from manytask.api import bp
    from manytask.ui_grades import serialize

    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_request_context():
        data = serialize(
            {
                "course_name": "a.b",
                "is_course_admin": False,
                "readonly_fields": ["username", "total_score"],
                "students": [{"first_name": "Private", "comment": "Secret"}],
                "app": object(),
            }
        )
    assert data == {
        "courseName": "a.b",
        "canEdit": False,
        "readOnlyFields": ["username", "total_score"],
        "urls": {
            "database": "/api/a.b/database",
            "updateScore": "/api/a.b/database/update",
            "updateComment": "/api/a.b/comment/update",
            "overrideGrade": "/api/a.b/grade/override",
            "clearGradeOverride": "/api/a.b/grade/clear_override",
        },
    }


def test_course_form_serializer_preserves_failed_post_without_course_context():
    from manytask.api import bp as api_bp
    from manytask.ui_course_admin import serialize_edit

    app = Flask(__name__)
    app.register_blueprint(instance_admin_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    with app.test_request_context(
        "/instance_admin/courses/a.b/edit",
        method="POST",
        data={"registration_secret": "draft", "gitlab_course_public_repo": "new/public", "token": "forged"},
    ):
        from flask import request

        request.view_args = {"course_name": "a.b"}
        data = serialize_edit({"error_message": "CSRF Error", "rms": "sourcecraft"})
    assert data["action"] == "/instance_admin/courses/a.b/edit"
    assert data["values"]["registration_secret"] == "draft"
    assert data["values"]["gitlab_course_public_repo"] == "new/public"
    assert "token" not in data["values"]
    assert data["accessUrls"] is None
    assert data["courseUsers"] == []


def test_course_edit_serializer_allows_only_displayed_user_fields():
    from manytask.api import bp as api_bp
    from manytask.ui_course_admin import serialize_edit

    app = Flask(__name__)
    app.register_blueprint(instance_admin_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    course = SimpleNamespace(
        course_name="a.b",
        namespace_id=4,
        registration_secret="secret",
        token="fixed",
        gitlab_course_group="g",
        gitlab_course_public_repo="g/public",
        gitlab_course_students_group="g/students",
        gitlab_default_branch="main",
        status=SimpleNamespace(value="in_progress"),
        show_allscores=False,
    )
    user = SimpleNamespace(username="alice", first_name="Alice", last_name="A", email="private@example.com")
    with app.test_request_context("/instance_admin/courses/a.b/edit"):
        data = serialize_edit({"course": course, "course_users": [(user, False)]})
    assert data["values"]["token"] == "fixed"
    assert data["courseUsers"] == [{"username": "alice", "firstName": "Alice", "lastName": "A"}]
    assert "private@example.com" not in str(data)
    assert data["accessUrls"] == {
        "users": "/api/a.b/access_users",
        "courseAdmin": "/api/a.b/course_admin",
    }


def test_course_create_serializer_keeps_unchecked_scores_after_failed_post():
    from manytask.ui_course_admin import serialize_create

    app = Flask(__name__)
    app.register_blueprint(instance_admin_bp)
    with app.test_request_context("/instance_admin/courses/new", method="POST", data={"namespace_id": "0"}):
        data = serialize_create({"generated_token": "server-generated"})
    assert data["showAllScores"] is False
    assert data["values"]["token"] == "server-generated"


def test_course_create_serializer_blocks_missing_namespace_path():
    from flask import session

    from manytask.ui_course_admin import serialize_create

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(instance_admin_bp)
    namespace = SimpleNamespace(id=4, name="Science", slug="science", gitlab_group_id=8)
    app.storage_api = SimpleNamespace(
        check_if_instance_admin=lambda _username: True,
        get_all_namespaces=lambda: [namespace],
    )

    def fail_path(_group_id):
        raise RuntimeError("RMS unavailable")

    app.rms_api = SimpleNamespace(get_group_path_by_id=fail_path)
    with app.test_request_context("/instance_admin/courses/new?namespace_id=4"):
        session["manytask"] = {"username": "admin"}
        data = serialize_create({"generated_token": "token"})
    assert data["namespaceError"] == "Could not load namespace paths. Please refresh the page."


def test_admin_serializers_allowlist_users_and_retain_namespace_course_fields():
    from manytask.api import namespace_bp
    from manytask.ui_administration import serialize_instance, serialize_namespace, serialize_namespaces

    expected_course_count = 3
    app = Flask(__name__)
    app.register_blueprint(instance_admin_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(namespace_bp)
    user = SimpleNamespace(
        user_id=2,
        username="alice",
        first_name="Alice",
        last_name="A",
        instance_admin=True,
        rms_id=42,
        email="private@example.com",
        token="private-token",
    )
    namespace = SimpleNamespace(id=1, name="Учебный</script>", slug="study", description=None, gitlab_group_id=12)
    ns_dict = {
        "id": 1,
        "name": namespace.name,
        "slug": "study",
        "description": None,
        "gitlab_group_id": 12,
        "users_count": 1,
        "courses_count": 3,
    }
    with app.test_request_context("/instance_admin/panel"):
        data = serialize_instance(
            {
                "users": [user],
                "namespaces": [ns_dict],
                "courses": [{"name": "Math", "url": "math", "namespace_slug": "study"}],
            }
        )
        assert data["users"] == [
            {"id": 2, "username": "alice", "firstName": "Alice", "lastName": "A", "instanceAdmin": True}
        ]
        assert data["courses"] == [
            {"name": "Math", "href": "/instance_admin/courses/math/edit", "namespaceSlug": "study"}
        ]
        assert data["namespaceApiUrl"] == "/api/namespaces"
        assert serialize_namespaces({"namespaces": [ns_dict]})["namespaces"][0]["coursesCount"] == expected_course_count
        panel = serialize_namespace(
            {
                "namespace": namespace,
                "users": [
                    {"id": 2, "username": "alice", "rms_id": 42, "role": "namespace_admin", "token": "private-token"}
                ],
                "available_users": [user],
                "courses": [
                    {
                        "id": 4,
                        "name": "math",
                        "url": "/math",
                        "owners_string": "alice",
                        "status": "running",
                        "gitlab_course_group": "g/math",
                    }
                ],
            }
        )
        assert panel["users"] == [{"id": 2, "username": "alice", "rmsId": 42, "role": "namespace_admin"}]
        assert panel["availableUsers"] == [{"id": 2, "username": "alice", "rmsId": 42}]
        assert panel["courses"] == [
            {
                "id": 4,
                "name": "math",
                "href": "/math",
                "owners": "alice",
                "status": "running",
                "gitlabGroup": "g/math",
                "editHref": "/instance_admin/courses/math/edit",
            }
        ]
        assert panel["namespace"]["usersCount"] == 1
        assert panel["usersUrl"] == "/api/namespaces/1/users"
        assert panel["createCourseUrl"] == "/instance_admin/courses/new?namespace_id=1"
    assert "private-token" not in str(data) + str(panel)
    assert "private@example.com" not in str(data) + str(panel)


def test_shared_profile_reads_current_users_saved_names():
    from flask import session

    from manytask.ui_shared import serialize_shared

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(instance_admin_bp)
    user = SimpleNamespace(first_name="Updated", last_name="Иванов", private_token="must-not-serialize")
    app.storage_api = SimpleNamespace(
        get_stored_user_by_username=lambda username: user if username == "alice" else None
    )
    with app.test_request_context("/"):
        session["manytask"] = {"username": "alice"}
        data = serialize_shared({})
        assert data["firstName"] == "Updated"
        assert data["lastName"] == "Иванов"
        assert "must-not-serialize" not in str(data)
