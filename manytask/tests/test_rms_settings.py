import time
from unittest.mock import MagicMock

import pytest

from manytask.course import ProtectedBranchSettings
from manytask.mock_rms import MockRmsApi, MockRmsGroup, MockRmsProject
from manytask.utils import rms_settings
from manytask.utils.rms_settings import reconcile_course_rms_settings, schedule_rms_settings_reconcile


class FakeCourse:
    def __init__(self, students_group, ci_config_path, protected_branches):
        self.gitlab_course_students_group = students_group
        self.ci_config_path = ci_config_path
        self.protected_branches = protected_branches


def _branches():
    return [
        ProtectedBranchSettings(
            name="main", push_access_level="developer", merge_access_level="developer", allow_force_push=True
        )
    ]


def _make_rms_api_with_projects(group_path, usernames):
    api = MockRmsApi("http://gitlab.test")
    group = MockRmsGroup(name=group_path)
    for username in usernames:
        project = MockRmsProject(name=username, group=group_path)
        api.projects[f"{group_path}/{username}"] = project
        group.projects[username] = project
    api.groups[group_path] = group
    return api


def test_reconcile_applies_settings_and_clears_pending():
    group_path = "group/students"
    api = _make_rms_api_with_projects(group_path, ["alice", "bob"])
    storage_api = MagicMock()
    storage_api.get_course.return_value = FakeCourse(group_path, ".gitlab-ci.yml@group/public", _branches())

    result = reconcile_course_rms_settings(storage_api, api, "test_course")

    assert result.checked == 2  # noqa: PLR2004
    assert result.changed == 2  # noqa: PLR2004
    assert result.failed == 0
    assert result.success is True
    storage_api.clear_rms_settings_pending.assert_called_once_with("test_course")


def test_reconcile_second_pass_is_idempotent():
    group_path = "group/students"
    api = _make_rms_api_with_projects(group_path, ["alice"])
    storage_api = MagicMock()
    storage_api.get_course.return_value = FakeCourse(group_path, ".gitlab-ci.yml@group/public", _branches())

    reconcile_course_rms_settings(storage_api, api, "test_course")
    result = reconcile_course_rms_settings(storage_api, api, "test_course")

    assert result.checked == 1
    assert result.changed == 0


def test_reconcile_reports_failures_and_leaves_pending():
    group_path = "group/students"
    api = _make_rms_api_with_projects(group_path, ["alice"])
    api.ensure_project_settings = MagicMock(side_effect=RuntimeError("boom"))
    storage_api = MagicMock()
    storage_api.get_course.return_value = FakeCourse(group_path, ".gitlab-ci.yml@group/public", _branches())

    result = reconcile_course_rms_settings(storage_api, api, "test_course")

    assert result.checked == 1
    assert result.changed == 0
    assert result.failed == 1
    assert result.success is False
    storage_api.clear_rms_settings_pending.assert_not_called()


def test_reconcile_unknown_course_raises():
    storage_api = MagicMock()
    storage_api.get_course.return_value = None
    api = MockRmsApi("http://gitlab.test")

    with pytest.raises(ValueError):
        reconcile_course_rms_settings(storage_api, api, "missing")


def test_schedule_skips_when_already_running():
    storage_api = MagicMock()
    api = MagicMock()

    with rms_settings._courses_in_progress_lock:
        rms_settings._courses_in_progress.add("busy_course")
    try:
        started = schedule_rms_settings_reconcile(storage_api, api, "busy_course")
        assert started is False
    finally:
        with rms_settings._courses_in_progress_lock:
            rms_settings._courses_in_progress.discard("busy_course")


def test_schedule_starts_background_reconcile_and_clears_pending():
    group_path = "group/students"
    api = _make_rms_api_with_projects(group_path, ["alice"])
    storage_api = MagicMock()
    storage_api.get_course.return_value = FakeCourse(group_path, ".gitlab-ci.yml@group/public", _branches())

    started = schedule_rms_settings_reconcile(storage_api, api, "threaded_course")
    assert started is True

    for _ in range(50):
        with rms_settings._courses_in_progress_lock:
            still_running = "threaded_course" in rms_settings._courses_in_progress
        if not still_running:
            break
        time.sleep(0.05)

    storage_api.clear_rms_settings_pending.assert_called_once_with("threaded_course")
