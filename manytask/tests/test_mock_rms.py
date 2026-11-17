import pytest

from manytask.abstract import RmsApiException
from manytask.course import ProtectedBranchSettings
from manytask.mock_rms import MockRmsApi
from tests.constants import (
    GITLAB_BASE_URL,
    TEST_EMAIL,
    TEST_FIRST_NAME,
    TEST_GROUP_NAME,
    TEST_LAST_NAME,
    TEST_PASSWORD,
    TEST_PUBLIC_REPO,
    TEST_STUDENTS_GROUP,
    TEST_USERNAME,
)

TEST_CI_CONFIG_PATH = f".gitlab-ci.yml@{TEST_GROUP_NAME}/{TEST_PUBLIC_REPO}"
TEST_PROTECTED_BRANCHES = [
    ProtectedBranchSettings(
        name="main", push_access_level="developer", merge_access_level="developer", allow_force_push=True
    )
]


def test_register_new_user():
    api = MockRmsApi(GITLAB_BASE_URL)
    api.register_new_user(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_EMAIL, TEST_PASSWORD)

    user = api.get_rms_user_by_username(TEST_USERNAME)
    assert user.username == TEST_USERNAME
    assert user.name == f"{TEST_FIRST_NAME} {TEST_LAST_NAME}"

    with pytest.raises(RmsApiException):
        api.get_rms_user_by_username("unknown")


def test_create_public_repo():
    api = MockRmsApi(GITLAB_BASE_URL)
    api.create_public_repo(TEST_GROUP_NAME, TEST_PUBLIC_REPO)

    assert api.check_project_exists(TEST_PUBLIC_REPO, TEST_GROUP_NAME) is True
    assert api.check_project_exists("unknown", TEST_GROUP_NAME) is False


def test_create_students_group():
    api = MockRmsApi(GITLAB_BASE_URL)
    api.create_students_group(TEST_STUDENTS_GROUP)

    # Just verify no exception is raised
    assert True


def test_create_project():
    api = MockRmsApi(GITLAB_BASE_URL)
    api.register_new_user(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_EMAIL, TEST_PASSWORD)
    user = api.get_rms_user_by_username(TEST_USERNAME)

    api.create_public_repo(TEST_GROUP_NAME, TEST_PUBLIC_REPO)
    api.create_students_group(TEST_STUDENTS_GROUP)
    api.create_project(user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES)

    assert api.check_project_exists(TEST_USERNAME, TEST_STUDENTS_GROUP) is True
    assert (
        api.get_url_for_repo(TEST_USERNAME, TEST_STUDENTS_GROUP)
        == f"{GITLAB_BASE_URL}/{TEST_STUDENTS_GROUP}/{TEST_USERNAME}"
    )

    project_path = f"{TEST_STUDENTS_GROUP}/{TEST_USERNAME}"
    assert api.project_settings[project_path]["ci_config_path"] == TEST_CI_CONFIG_PATH
    assert api.list_group_projects(TEST_STUDENTS_GROUP) == [project_path]


def test_create_project_existing_project_updates_settings():
    api = MockRmsApi(GITLAB_BASE_URL)
    api.register_new_user(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_EMAIL, TEST_PASSWORD)
    user = api.get_rms_user_by_username(TEST_USERNAME)

    api.create_public_repo(TEST_GROUP_NAME, TEST_PUBLIC_REPO)
    api.create_students_group(TEST_STUDENTS_GROUP)
    api.create_project(user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES)

    new_ci_config_path = ".gitlab-ci.yml@other/repo"
    api.create_project(user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, new_ci_config_path, TEST_PROTECTED_BRANCHES)

    project_path = f"{TEST_STUDENTS_GROUP}/{TEST_USERNAME}"
    assert api.project_settings[project_path]["ci_config_path"] == new_ci_config_path


def test_ensure_project_settings_no_change_returns_false():
    api = MockRmsApi(GITLAB_BASE_URL)
    project_path = "group/project"

    assert api.ensure_project_settings(project_path, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES) is True
    assert api.ensure_project_settings(project_path, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES) is False


def test_list_group_projects_unknown_group_returns_empty():
    api = MockRmsApi(GITLAB_BASE_URL)
    assert api.list_group_projects("unknown/group") == []
