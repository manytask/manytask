from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from gitlab import GitlabGetError, const
from gitlab.v4.objects import Group, GroupMember, Project, ProjectFork, User
from requests import HTTPError

from manytask.glab import GitLabApi, GitLabApiException, GitLabConfig, RmsUser
from tests import constants


# Shared fixture logic
def create_mock_gitlab_group(group_id: int, name_short: str, name_full: str) -> Group:
    """
    Creates a mock gitlab Group object with specified properties.

    Args:
        group_id (int): The unique identifier for the group.
        name_short (str): The short or abbreviated name of the group.
        name_full (str): The full, descriptive name of the group.
    """

    group = mock.create_autospec(Group, instance=True)
    group.id = group_id
    group.name = name_short
    group.full_name = name_full
    return group


def create_mock_gitlab_project(project_id: int, namespace: str) -> Project:
    """
    Creates a mock gitlab Project object with specified properties.

    Args:
        project_id (int): The unique identifier for the project.
        namespace (str): The namespace or path with namespace for the project.
    """

    project = MagicMock()
    project.path_with_namespace = namespace
    project.id = project_id
    return project


@pytest.fixture
def mock_rms_user() -> RmsUser:
    """Fixture to create a mock RmsUser object."""
    return RmsUser(
        id=constants.TEST_USER_ID,
        username=constants.TEST_USERNAME,
        name=constants.TEST_USERNAME,
    )


@pytest.fixture
def mock_gitlab_fork() -> ProjectFork:
    """Fixture to create a mock ProjectFork object."""
    fork = mock.create_autospec(ProjectFork, instance=True)
    fork.id = constants.TEST_FORK_ID
    fork.username = f"{constants.TEST_GROUP_STUDENT_NAME_SHORT}/{constants.TEST_USERNAME}"
    return fork


@pytest.fixture
def mock_gitlab_group_member() -> GroupMember:
    """Fixture to create a mock GroupMember object."""
    member = mock.create_autospec(GroupMember, instance=True)
    member.id = constants.TEST_USER_ID
    member.username = constants.TEST_USERNAME
    return member


@pytest.fixture
def mock_gitlab_group() -> Group:
    """Fixture to create a mock course group."""
    return create_mock_gitlab_group(
        constants.TEST_GROUP_ID, constants.TEST_GROUP_NAME_SHORT, constants.TEST_GROUP_NAME_FULL
    )


@pytest.fixture
def mock_gitlab_group_public() -> Group:
    """Fixture to create a mock public group."""
    return create_mock_gitlab_group(
        constants.TEST_GROUP_ID_PUBLIC, constants.TEST_GROUP_PUBLIC_NAME_SHORT, constants.TEST_GROUP_PUBLIC_NAME_FULL
    )


@pytest.fixture
def mock_gitlab_group_student() -> Group:
    """Fixture to create a mock student group."""
    return create_mock_gitlab_group(
        constants.TEST_GROUP_ID_STUDENT, constants.TEST_GROUP_STUDENT_NAME_SHORT, constants.TEST_GROUP_STUDENT_NAME_FULL
    )


@pytest.fixture
def mock_gitlab_project(mock_gitlab_group_member: GroupMember) -> Project:
    """Fixture to create a mock project with a group member."""
    project = create_mock_gitlab_project(constants.TEST_PROJECT_ID, constants.TEST_PROJECT_FULL_NAME)
    return project


@pytest.fixture
def mock_gitlab_student_project(mock_gitlab_group_member: GroupMember) -> Project:
    """Fixture to create a mock student project."""
    project = create_mock_gitlab_project(
        constants.TEST_PROJECT_ID + 1, f"{constants.TEST_GROUP_STUDENT_NAME}/{constants.TEST_USERNAME}"
    )
    project.members.create = MagicMock(return_value=mock_gitlab_group_member)
    return project


@pytest.fixture
def mock_gitlab_public_project() -> Project:
    """Fixture to create a mock public project."""
    return create_mock_gitlab_project(constants.TEST_PROJECT_ID + 2, constants.TEST_GROUP_PUBLIC_NAME)


@pytest.fixture
def mock_gitlab_user() -> User:
    """Fixture to create a mock GitLab user."""
    user = mock.create_autospec(User, instance=True)
    user.id = constants.TEST_USER_ID
    user.name = constants.TEST_USERNAME
    user.username = constants.TEST_USERNAME
    user.email = constants.TEST_USER_EMAIL
    user.web_url = constants.TEST_USER_URL
    return user


@pytest.fixture
def mock_gitlab():
    """Fixture to setup the patched GitLab instance."""
    with patch("gitlab.Gitlab") as MockGitlab:
        yield MockGitlab


@pytest.fixture
def gitlab(
    mock_gitlab,
    mock_gitlab_group,
    mock_gitlab_project,
    mock_gitlab_public_project,
    mock_gitlab_group_student,
):
    """Fixture to set up the GitLabApi with mocked GitLab objects."""
    mock_gitlab_instance = mock_gitlab.return_value
    mock_gitlab_instance.groups.list.return_value = [mock_gitlab_group, mock_gitlab_group_student]
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_project, mock_gitlab_public_project]

    api = GitLabApi(
        GitLabConfig(
            base_url="http://example.com",
            admin_token="admin-token",
        )
    )
    return api, mock_gitlab_instance


def test_register_new_user(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab

    username = constants.TEST_USERNAME
    firstname = constants.TEST_USER_FIRSTNAME
    lastname = constants.TEST_USER_LASTNAME
    email = constants.TEST_USER_EMAIL
    password = constants.TEST_USER_PASSWORD

    gitlab_api.register_new_user(username, firstname, lastname, email, password)

    mock_gitlab_instance.users.create.assert_called_once_with(
        {
            "email": email,
            "username": username,
            "name": f"{firstname} {lastname}",
            "external": False,
            "password": password,
            "skip_confirmation": True,
        }
    )


def test_get_project_by_name_success(gitlab, mock_gitlab_project):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_project]

    project = gitlab_api._get_project_by_name(constants.TEST_PROJECT_FULL_NAME)

    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=constants.TEST_PROJECT_NAME)
    assert project.path_with_namespace == constants.TEST_PROJECT_FULL_NAME


def test_create_public_repo(gitlab, mock_gitlab_group, mock_gitlab_project):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = [mock_gitlab_group]
    mock_gitlab_instance.projects.list.return_value = []
    mock_gitlab_instance.projects.create.return_value = mock_gitlab_project

    gitlab_api.create_public_repo(constants.TEST_GROUP_NAME, constants.TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.create.assert_called_once_with(
        {
            "name": constants.TEST_GROUP_PUBLIC_NAME,
            "path": constants.TEST_GROUP_PUBLIC_NAME,
            "namespace_id": mock_gitlab_group.id,
            "visibility": "public",
            "shared_runners_enabled": True,
            "auto_devops_enabled": False,
            "initialize_with_readme": True,
        }
    )


def test_create_public_already_exist_repo(gitlab, mock_gitlab_group, mock_gitlab_public_project):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = [mock_gitlab_group]
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_public_project]

    gitlab_api.create_public_repo(constants.TEST_GROUP_NAME, constants.TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.create.assert_not_called()


def test_create_students_group(gitlab, mock_gitlab_group):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = []
    mock_gitlab_instance.groups.create.return_value = mock_gitlab_group

    gitlab_api.create_students_group(constants.TEST_GROUP_NAME)

    mock_gitlab_instance.groups.create.assert_called_once_with(
        {
            "name": constants.TEST_GROUP_NAME,
            "path": constants.TEST_GROUP_NAME,
            "visibility": "private",
            "lfs_enabled": True,
            "shared_runners_enabled": True,
        }
    )


def test_get_group_by_name_success(gitlab, mock_gitlab_group):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = [mock_gitlab_group]

    result = gitlab_api._get_group_by_name(constants.TEST_GROUP_NAME)

    assert result.name == mock_gitlab_group.name
    assert result.full_name == mock_gitlab_group.full_name


def test_get_project_by_name_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = []

    with pytest.raises(RuntimeError, match=f"Unable to find project {constants.TEST_PROJECT_FULL_NAME}"):
        gitlab_api._get_project_by_name(constants.TEST_PROJECT_FULL_NAME)


def test_get_group_by_name_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = []

    with pytest.raises(RuntimeError, match=f"Unable to find group {constants.TEST_GROUP_NAME}"):
        gitlab_api._get_group_by_name(constants.TEST_GROUP_NAME)


def test_check_project_exists(gitlab, mock_gitlab_student_project):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_student_project]

    exists = gitlab_api.check_project_exists(constants.TEST_USERNAME, constants.TEST_GROUP_STUDENT_NAME)

    assert exists is True
    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=constants.TEST_USERNAME)


def test_check_project_not_exists(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = []

    exists = gitlab_api.check_project_exists(constants.TEST_USERNAME, constants.TEST_GROUP_NAME)

    assert exists is False
    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=constants.TEST_USERNAME)


def test_create_project_existing_project(gitlab, mock_rms_user, mock_gitlab_student_project, mock_gitlab_group_member):
    rms_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_student_project]
    mock_gitlab_instance.projects.get.return_value = mock_gitlab_student_project
    mock_gitlab_student_project.members.create.return_value = mock_gitlab_group_member

    rms_api.create_project(mock_rms_user, constants.TEST_GROUP_STUDENT_NAME, constants.TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=mock_rms_user.username)
    mock_gitlab_instance.projects.get.assert_called_with(mock_gitlab_student_project.id)
    mock_gitlab_student_project.members.create.assert_called_once_with(
        {"user_id": mock_rms_user.id, "access_level": const.AccessLevel.DEVELOPER}
    )


def test_create_project_no_existing_project_creates_fork(
    gitlab, mock_rms_user, mock_gitlab_group, mock_gitlab_student_project, mock_gitlab_fork
):
    rms_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = []
    rms_api._get_group_by_name = MagicMock(return_value=mock_gitlab_group)
    rms_api._get_project_by_name = MagicMock(return_value=mock_gitlab_student_project)
    mock_gitlab_student_project.forks.create.return_value = mock_gitlab_fork

    rms_api.create_project(mock_rms_user, constants.TEST_GROUP_STUDENT_NAME, constants.TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=mock_rms_user.username)
    rms_api._get_project_by_name.assert_called_with(constants.TEST_GROUP_PUBLIC_NAME)
    rms_api._get_group_by_name.assert_called_with(constants.TEST_GROUP_STUDENT_NAME)


def test_construct_rms_user(gitlab, mock_rms_user):
    gitlab_api, _ = gitlab
    user_dict = {
        "id": constants.TEST_USER_ID,
        "username": constants.TEST_USERNAME,
        "name": constants.TEST_USERNAME,
    }
    rms_user = gitlab_api._construct_rms_user(user_dict)

    assert rms_user == mock_rms_user


def test_get_student_by_username_found(gitlab, mock_rms_user):
    gitlab_api, _ = gitlab
    gitlab_api._get_rms_users_by_username = MagicMock(return_value=[mock_rms_user])

    result_rms_user = gitlab_api.get_rms_user_by_username(constants.TEST_USERNAME)

    assert result_rms_user == mock_rms_user
    gitlab_api._get_rms_users_by_username.assert_called_once_with(constants.TEST_USERNAME)


def test_get_student_by_username_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.users.list.return_value = []

    with pytest.raises(GitLabApiException, match=f"No users found for username {constants.TEST_USERNAME}"):
        gitlab_api.get_rms_user_by_username(constants.TEST_USERNAME)


def test_get_student_found(gitlab, mock_gitlab_user, mock_rms_user):
    rms_api, mock_gitlab_instance = gitlab
    user_attrs = {
        "id": constants.TEST_USER_ID,
        "username": "test_username",
        "name": "Test User",
        "course_group": constants.TEST_GROUP_NAME,
        "course_students_group": constants.TEST_GROUP_STUDENT_NAME,
    }
    mock_gitlab_user = MagicMock(_attrs=user_attrs)
    mock_gitlab_instance.users.get = MagicMock(return_value=mock_gitlab_user)
    rms_api._construct_rms_user = MagicMock(return_value=mock_rms_user)

    rms_user = rms_api.get_rms_user_by_id(constants.TEST_USER_ID)

    assert rms_user == mock_rms_user
    mock_gitlab_instance.users.get.assert_called_once_with(constants.TEST_USER_ID)
    rms_api._construct_rms_user.assert_called_once_with(user_attrs)


def test_get_student_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.users.get = MagicMock(side_effect=GitlabGetError("User not found"))

    with pytest.raises(GitlabGetError, match="User not found"):
        gitlab_api.get_rms_user_by_id(constants.TEST_USER_ID)

    mock_gitlab_instance.users.get.assert_called_once_with(constants.TEST_USER_ID)


@patch("requests.get")
def test_get_authenticated_student_success(mock_get, gitlab, mock_rms_user):
    rms_api, _ = gitlab
    oauth_token = "valid_oauth_token"
    headers = {"Authorization": f"Bearer {oauth_token}"}

    user_data = {
        "id": constants.TEST_USER_ID,
        "username": constants.TEST_USERNAME,
        "name": constants.TEST_USERNAME,
    }
    mock_response = MagicMock()
    mock_response.json.return_value = user_data
    mock_response.raise_for_status = MagicMock()

    mock_get.return_value = mock_response
    rms_api._construct_rms_user = MagicMock(return_value=mock_rms_user)

    rms_user = rms_api.get_authenticated_rms_user(oauth_token)

    assert rms_user == mock_rms_user
    mock_get.assert_called_once_with(f"{rms_api.base_url}/api/v4/user", headers=headers)
    rms_api._construct_rms_user.assert_called_once_with(user_data)


@patch("requests.get")
def test_get_authenticated_student_failure(mock_get, gitlab):
    gitlab_api, _ = gitlab
    oauth_token = "invalid_oauth_token"
    headers = {"Authorization": f"Bearer {oauth_token}"}

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = HTTPError("401 Unauthorized")

    mock_get.return_value = mock_response

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        gitlab_api.get_authenticated_rms_user(oauth_token)

    mock_get.assert_called_once_with(f"{gitlab_api.base_url}/api/v4/user", headers=headers)


def test_get_url_for_task_base(gitlab):
    gitlab_api, _ = gitlab
    url = gitlab_api.get_url_for_task_base(constants.TEST_GROUP_PUBLIC_NAME, constants.TEST_GROUP_PUBLIC_DEFAULT_BRANCH)

    assert (
        url
        == f"{gitlab_api.base_url}/{constants.TEST_GROUP_PUBLIC_NAME}/blob/{constants.TEST_GROUP_PUBLIC_DEFAULT_BRANCH}"
    )


def test_get_url_for_repo(gitlab):
    gitlab_api, _ = gitlab
    url = gitlab_api.get_url_for_repo(constants.TEST_USERNAME, constants.TEST_GROUP_STUDENT_NAME)

    assert url == f"{gitlab_api.base_url}/{constants.TEST_GROUP_STUDENT_NAME}/{constants.TEST_USERNAME}"
