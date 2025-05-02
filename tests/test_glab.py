from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from gitlab import GitlabGetError, const
from gitlab.v4.objects import Group, GroupMember, Project, ProjectFork
from requests import HTTPError

from manytask.glab import GitLabApi, GitLabApiException, GitLabConfig, Student, User, map_gitlab_user_to_student

# Constants for test data
EXAMPLE_REPO_OWNER = "example_owner"
EXAMPLE_REPO_NAME = "example_repo"
EXAMPLE_HVCS_DOMAIN = "example.com"

TEST_USER_ID = 1
TEST_USERNAME = "TestUser"
TEST_USER_EMAIL = "test-email@test.ru"
TEST_USER_PASSWORD = "testpassword"
TEST_USER_FIRSTNAME = "testfirstname"
TEST_USER_LASTNAME = "testlastname"
TEST_USER_URL = "example_repo"

TEST_PROJECT_ID = 1
TEST_PROJECT_NAME = "TestProject"
TEST_PROJECT_FULL_NAME = "some/TestGroup/TestProject"

TEST_GROUP_ID = 1
TEST_GROUP_NAME = "some/TestGroup"
TEST_GROUP_NAME_SHORT = "TestGroup"
TEST_GROUP_NAME_FULL = "some / TestGroup"

TEST_GROUP_ID_PUBLIC = 2
TEST_GROUP_PUBLIC_NAME = "some/TestGroup/TestProject/Public"
TEST_GROUP_PUBLIC_NAME_SHORT = "Public"
TEST_GROUP_PUBLIC_NAME_FULL = "some / TestGroup / TestProject / Public"
TEST_GROUP_PUBLIC_DEFAULT_BRANCH = "main"

TEST_GROUP_ID_STUDENT = 3
TEST_GROUP_STUDENT_NAME = "some/TestGroup/TestProject/Students"
TEST_GROUP_STUDENT_NAME_SHORT = "Students"
TEST_GROUP_STUDENT_NAME_FULL = "some / TestGroup / TestProject / Students"

TEST_FORK_ID = 1


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
def mock_student() -> Student:
    """Fixture to create a mock Student object."""
    return Student(
        id=TEST_USER_ID,
        username=TEST_USERNAME,
        name=TEST_USERNAME,
    )


@pytest.fixture
def mock_user() -> User:
    """Fixture to create a mock User object."""
    return User(
        username=TEST_USERNAME,
        firstname=TEST_USER_FIRSTNAME,
        lastname=TEST_USER_LASTNAME,
        email=TEST_USER_EMAIL,
        password=TEST_USER_PASSWORD,
    )


@pytest.fixture
def mock_gitlab_fork() -> ProjectFork:
    """Fixture to create a mock ProjectFork object."""
    fork = mock.create_autospec(ProjectFork, instance=True)
    fork.id = TEST_FORK_ID
    fork.username = f"{TEST_GROUP_STUDENT_NAME_SHORT}/{TEST_USERNAME}"
    return fork


@pytest.fixture
def mock_gitlab_group_member() -> GroupMember:
    """Fixture to create a mock GroupMember object."""
    member = mock.create_autospec(GroupMember, instance=True)
    member.id = TEST_USER_ID
    member.username = TEST_USERNAME
    return member


@pytest.fixture
def mock_gitlab_group() -> Group:
    """Fixture to create a mock course group."""
    return create_mock_gitlab_group(TEST_GROUP_ID, TEST_GROUP_NAME_SHORT, TEST_GROUP_NAME_FULL)


@pytest.fixture
def mock_gitlab_group_public() -> Group:
    """Fixture to create a mock public group."""
    return create_mock_gitlab_group(TEST_GROUP_ID_PUBLIC, TEST_GROUP_PUBLIC_NAME_SHORT, TEST_GROUP_PUBLIC_NAME_FULL)


@pytest.fixture
def mock_gitlab_group_student() -> Group:
    """Fixture to create a mock student group."""
    return create_mock_gitlab_group(TEST_GROUP_ID_STUDENT, TEST_GROUP_STUDENT_NAME_SHORT, TEST_GROUP_STUDENT_NAME_FULL)


@pytest.fixture
def mock_gitlab_project(mock_gitlab_group_member: GroupMember) -> Project:
    """Fixture to create a mock project with a group member."""
    project = create_mock_gitlab_project(TEST_PROJECT_ID, TEST_PROJECT_FULL_NAME)
    return project


@pytest.fixture
def mock_gitlab_student_project(mock_gitlab_group_member: GroupMember) -> Project:
    """Fixture to create a mock student project."""
    project = create_mock_gitlab_project(TEST_PROJECT_ID + 1, f"{TEST_GROUP_STUDENT_NAME}/{TEST_USERNAME}")
    project.members.create = MagicMock(return_value=mock_gitlab_group_member)
    return project


@pytest.fixture
def mock_gitlab_public_project() -> Project:
    """Fixture to create a mock public project."""
    return create_mock_gitlab_project(TEST_PROJECT_ID + 2, TEST_GROUP_PUBLIC_NAME)


@pytest.fixture
def mock_gitlab_user() -> User:
    """Fixture to create a mock GitLab user."""
    user = mock.create_autospec(User, instance=True)
    user.id = TEST_USER_ID
    user.name = TEST_USERNAME
    user.username = TEST_USERNAME
    user.email = TEST_USER_EMAIL
    user.web_url = TEST_USER_URL
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


def test_register_new_user(gitlab, mock_gitlab_user, mock_user):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.users.create.return_value = mock_gitlab_user

    new_user = gitlab_api.register_new_user(mock_user)

    mock_gitlab_instance.users.create.assert_called_once_with(
        {
            "email": mock_user.email,
            "username": mock_user.username,
            "name": f"{mock_user.firstname} {mock_user.lastname}",
            "external": False,
            "password": mock_user.password,
            "skip_confirmation": True,
        }
    )

    assert new_user.username == mock_gitlab_user.username
    assert new_user.email == mock_gitlab_user.email


def test_get_project_by_name_success(gitlab, mock_gitlab_project):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_project]

    project = gitlab_api._get_project_by_name(TEST_PROJECT_FULL_NAME)

    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=TEST_PROJECT_NAME)
    assert project.path_with_namespace == TEST_PROJECT_FULL_NAME


def test_create_public_repo(gitlab, mock_gitlab_group, mock_gitlab_project):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = [mock_gitlab_group]
    mock_gitlab_instance.projects.list.return_value = []
    mock_gitlab_instance.projects.create.return_value = mock_gitlab_project

    gitlab_api.create_public_repo(TEST_GROUP_NAME, TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.create.assert_called_once_with(
        {
            "name": TEST_GROUP_PUBLIC_NAME,
            "path": TEST_GROUP_PUBLIC_NAME,
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

    gitlab_api.create_public_repo(TEST_GROUP_NAME, TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.create.assert_not_called()


def test_create_students_group(gitlab, mock_gitlab_group):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = []
    mock_gitlab_instance.groups.create.return_value = mock_gitlab_group

    gitlab_api.create_students_group(TEST_GROUP_NAME)

    mock_gitlab_instance.groups.create.assert_called_once_with(
        {
            "name": TEST_GROUP_NAME,
            "path": TEST_GROUP_NAME,
            "visibility": "private",
            "lfs_enabled": True,
            "shared_runners_enabled": True,
        }
    )


def test_get_group_by_name_success(gitlab, mock_gitlab_group):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = [mock_gitlab_group]

    result = gitlab_api._get_group_by_name(TEST_GROUP_NAME)

    assert result.name == mock_gitlab_group.name
    assert result.full_name == mock_gitlab_group.full_name


def test_get_project_by_name_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = []

    with pytest.raises(RuntimeError, match=f"Unable to find project {TEST_PROJECT_FULL_NAME}"):
        gitlab_api._get_project_by_name(TEST_PROJECT_FULL_NAME)


def test_get_group_by_name_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.groups.list.return_value = []

    with pytest.raises(RuntimeError, match=f"Unable to find group {TEST_GROUP_NAME}"):
        gitlab_api._get_group_by_name(TEST_GROUP_NAME)


def test_check_project_exists(gitlab, mock_gitlab_student_project, mock_student):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_student_project]

    exists = gitlab_api.check_project_exists(mock_student, TEST_GROUP_STUDENT_NAME)

    assert exists is True
    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=mock_student.username)


def test_check_project_not_exists(gitlab, mock_student):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = []

    exists = gitlab_api.check_project_exists(mock_student, TEST_GROUP_NAME)

    assert exists is False
    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=mock_student.username)


def test_create_project_existing_project(gitlab, mock_student, mock_gitlab_student_project, mock_gitlab_group_member):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = [mock_gitlab_student_project]
    mock_gitlab_instance.projects.get.return_value = mock_gitlab_student_project
    mock_gitlab_student_project.members.create.return_value = mock_gitlab_group_member

    gitlab_api.create_project(mock_student, TEST_GROUP_STUDENT_NAME, TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=mock_student.username)
    mock_gitlab_instance.projects.get.assert_called_with(mock_gitlab_student_project.id)
    mock_gitlab_student_project.members.create.assert_called_once_with(
        {"user_id": mock_student.id, "access_level": const.AccessLevel.DEVELOPER}
    )


def test_create_project_no_existing_project_creates_fork(
    gitlab, mock_student, mock_gitlab_group, mock_gitlab_student_project, mock_gitlab_fork
):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.projects.list.return_value = []
    gitlab_api._get_group_by_name = MagicMock(return_value=mock_gitlab_group)
    gitlab_api._get_project_by_name = MagicMock(return_value=mock_gitlab_student_project)
    mock_gitlab_student_project.forks.create.return_value = mock_gitlab_fork

    gitlab_api.create_project(mock_student, TEST_GROUP_STUDENT_NAME, TEST_GROUP_PUBLIC_NAME)

    mock_gitlab_instance.projects.list.assert_called_with(get_all=True, search=mock_student.username)
    gitlab_api._get_project_by_name.assert_called_with(TEST_GROUP_PUBLIC_NAME)
    gitlab_api._get_group_by_name.assert_called_with(TEST_GROUP_STUDENT_NAME)


def test_check_is_course_admin(gitlab):
    gitlab_api, _ = gitlab
    mock_group = MagicMock()
    gitlab_api._get_group_by_name = MagicMock(return_value=mock_group)
    mock_member = MagicMock()
    mock_group.members_all.get.return_value = mock_member

    is_admin = gitlab_api.check_is_course_admin(TEST_USER_ID, TEST_GROUP_NAME)

    assert is_admin is True


def test_check_is_course_admin_not_found(gitlab):
    gitlab_api, _ = gitlab
    mock_group = MagicMock()
    gitlab_api._get_group_by_name = MagicMock(return_value=mock_group)
    mock_group.members_all.get.return_value = None

    is_admin = gitlab_api.check_is_course_admin(TEST_USER_ID, TEST_GROUP_NAME)

    assert is_admin is False


def test_parse_user_to_student(gitlab, mock_student):
    gitlab_api, _ = gitlab
    user_dict = {
        "id": TEST_USER_ID,
        "username": TEST_USERNAME,
        "name": TEST_USERNAME,
    }
    student = gitlab_api._parse_user_to_student(user_dict)

    assert student == mock_student


def test_get_student_by_username_found(gitlab, mock_student):
    gitlab_api, _ = gitlab
    gitlab_api.get_students_by_username = MagicMock(return_value=[mock_student])

    result_student = gitlab_api.get_student_by_username(TEST_USERNAME)

    assert result_student == mock_student
    gitlab_api.get_students_by_username.assert_called_once_with(TEST_USERNAME)


def test_get_student_by_username_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.users.list.return_value = []

    with pytest.raises(GitLabApiException, match=f"No students found for username {TEST_USERNAME}"):
        gitlab_api.get_student_by_username(TEST_USERNAME)


def test_get_student_found(gitlab, mock_user, mock_student):
    gitlab_api, mock_gitlab_instance = gitlab
    user_attrs = {
        "id": TEST_USER_ID,
        "username": "test_username",
        "name": "Test User",
        "course_group": TEST_GROUP_NAME,
        "course_students_group": TEST_GROUP_STUDENT_NAME,
    }
    mock_user = MagicMock(_attrs=user_attrs)
    mock_gitlab_instance.users.get = MagicMock(return_value=mock_user)
    gitlab_api._parse_user_to_student = MagicMock(return_value=mock_student)

    student = gitlab_api.get_student(TEST_USER_ID)

    assert student == mock_student
    mock_gitlab_instance.users.get.assert_called_once_with(TEST_USER_ID)
    gitlab_api._parse_user_to_student.assert_called_once_with(user_attrs)


def test_get_student_not_found(gitlab):
    gitlab_api, mock_gitlab_instance = gitlab
    mock_gitlab_instance.users.get = MagicMock(side_effect=GitlabGetError("User not found"))

    with pytest.raises(GitlabGetError, match="User not found"):
        gitlab_api.get_student(TEST_USER_ID)

    mock_gitlab_instance.users.get.assert_called_once_with(TEST_USER_ID)


@patch("requests.get")
def test_get_authenticated_student_success(mock_get, gitlab, mock_student):
    gitlab_api, _ = gitlab
    oauth_token = "valid_oauth_token"
    headers = {"Authorization": f"Bearer {oauth_token}"}

    user_data = {
        "id": TEST_USER_ID,
        "username": TEST_USERNAME,
        "name": TEST_USERNAME,
    }
    mock_response = MagicMock()
    mock_response.json.return_value = user_data
    mock_response.raise_for_status = MagicMock()

    mock_get.return_value = mock_response
    gitlab_api._parse_user_to_student = MagicMock(return_value=mock_student)

    student = gitlab_api.get_authenticated_student(oauth_token)

    assert student == mock_student
    mock_get.assert_called_once_with(f"{gitlab_api.base_url}/api/v4/user", headers=headers)
    gitlab_api._parse_user_to_student.assert_called_once_with(user_data)


@patch("requests.get")
def test_get_authenticated_student_failure(mock_get, gitlab):
    gitlab_api, _ = gitlab
    oauth_token = "invalid_oauth_token"
    headers = {"Authorization": f"Bearer {oauth_token}"}

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = HTTPError("401 Unauthorized")

    mock_get.return_value = mock_response

    with pytest.raises(HTTPError, match="401 Unauthorized"):
        gitlab_api.get_authenticated_student(oauth_token)

    mock_get.assert_called_once_with(f"{gitlab_api.base_url}/api/v4/user", headers=headers)


def test_get_url_for_task_base(gitlab):
    gitlab_api, _ = gitlab
    url = gitlab_api.get_url_for_task_base(TEST_GROUP_PUBLIC_NAME, TEST_GROUP_PUBLIC_DEFAULT_BRANCH)

    assert url == f"{gitlab_api.base_url}/{TEST_GROUP_PUBLIC_NAME}/blob/{TEST_GROUP_PUBLIC_DEFAULT_BRANCH}"


def test_get_url_for_repo(gitlab):
    gitlab_api, _ = gitlab
    url = gitlab_api.get_url_for_repo(TEST_USERNAME, TEST_GROUP_STUDENT_NAME)

    assert url == f"{gitlab_api.base_url}/{TEST_GROUP_STUDENT_NAME}/{TEST_USERNAME}"


def test_map_gitlab_user_to_student(gitlab, mock_gitlab_user):
    student = map_gitlab_user_to_student(mock_gitlab_user)

    assert student.username == TEST_USERNAME
    assert student.name == TEST_USERNAME
