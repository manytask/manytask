from manytask.course import (
    Course,
    CourseConfig,
    CourseStatus,
    ProtectedBranchSettings,
    resolve_effective_ci_config_path,
    resolve_effective_protected_branches,
)


class TestTask:
    def test_dummy(self) -> None:
        assert True


def test_resolve_effective_ci_config_path_uses_configured_value():
    assert resolve_effective_ci_config_path("custom/path.yml@group/repo", "group/repo") == "custom/path.yml@group/repo"


def test_resolve_effective_ci_config_path_defaults_to_public_repo():
    assert resolve_effective_ci_config_path(None, "group/repo") == ".gitlab-ci.yml@group/repo"


def test_resolve_effective_protected_branches_uses_configured_value():
    configured = [
        ProtectedBranchSettings(
            name="release", push_access_level="maintainer", merge_access_level="maintainer", allow_force_push=False
        )
    ]

    assert resolve_effective_protected_branches(configured, "main") == configured


def test_resolve_effective_protected_branches_defaults_to_default_branch():
    result = resolve_effective_protected_branches(None, "main")

    assert result == [
        ProtectedBranchSettings(
            name="main", push_access_level="developer", merge_access_level="developer", allow_force_push=True
        )
    ]


def _course_config(**overrides):
    defaults = dict(
        course_name="test_course",
        namespace_id=None,
        gitlab_course_group="group",
        gitlab_course_public_repo="group/public",
        gitlab_course_students_group="group/students",
        gitlab_default_branch="main",
        registration_secret="secret",
        token="token",
        show_allscores=True,
        status=CourseStatus.CREATED,
    )
    defaults.update(overrides)
    return CourseConfig(**defaults)


def test_course_ci_config_path_defaults_when_not_configured():
    course = Course(_course_config())

    assert course.ci_config_path == ".gitlab-ci.yml@group/public"


def test_course_ci_config_path_uses_configured_value():
    course = Course(_course_config(ci_config_path="custom.yml@group/other"))

    assert course.ci_config_path == "custom.yml@group/other"


def test_course_protected_branches_defaults_when_not_configured():
    course = Course(_course_config())

    assert course.protected_branches == [
        ProtectedBranchSettings(
            name="main", push_access_level="developer", merge_access_level="developer", allow_force_push=True
        )
    ]


def test_course_protected_branches_uses_configured_value():
    configured = [
        ProtectedBranchSettings(
            name="release", push_access_level="no_access", merge_access_level="maintainer", allow_force_push=False
        )
    ]
    course = Course(_course_config(protected_branches=configured))

    assert course.protected_branches == configured
