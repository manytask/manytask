import pytest

from manytask.abstract import RmsApiException
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
    api.create_project(user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO)

    assert api.check_project_exists(TEST_USERNAME, TEST_STUDENTS_GROUP) is True
    assert (
        api.get_url_for_repo(TEST_USERNAME, TEST_STUDENTS_GROUP)
        == f"{GITLAB_BASE_URL}/{TEST_STUDENTS_GROUP}/{TEST_USERNAME}"
    )


def test_authenticated_user():
    api = MockRmsApi(GITLAB_BASE_URL)
    api.register_new_user(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_EMAIL, TEST_PASSWORD)
    user = api.get_authenticated_rms_user("dummy-token")
    assert user.username == TEST_USERNAME
