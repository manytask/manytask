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
