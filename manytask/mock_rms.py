from dataclasses import dataclass, field
from typing import Dict, List

from authlib.integrations.flask_client import OAuth

from .abstract import RmsApi, RmsApiException, RmsUser


@dataclass
class MockRmsProject:
    name: str
    group: str
    visibility: str = "private"
    members: List[int] = field(default_factory=list)  # List of user IDs


@dataclass
class MockRmsGroup:
    name: str
    projects: Dict[str, MockRmsProject] = field(default_factory=dict)


class MockRmsApi(RmsApi):
    def __init__(self, base_url: str):
        self._base_url = base_url
        self.users: Dict[int, RmsUser] = {}
        self.users_by_username: Dict[str, RmsUser] = {}
        self.groups: Dict[str, MockRmsGroup] = {}
        self.projects: Dict[str, MockRmsProject] = {}  # key: "group/project"
        self.last_user: int = -1

    @property
    def base_url(self) -> str:
        return self._base_url

    def register_new_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
    ) -> RmsUser:
        if username in self.users_by_username:
            raise RmsApiException(f"User with username {username} already exists")

        user_id = max(self.users.keys(), default=0) + 1
        user: RmsUser = RmsUser(id=user_id, username=username, name=f"{firstname} {lastname}")
        self.users[user_id] = user
        self.users_by_username[username] = user
        self.last_user = user_id
        return user

    def create_public_repo(
        self,
        course_group: str,
        course_public_repo: str,
    ) -> None:
        project_path = f"{course_group}/{course_public_repo}"
        if project_path in self.projects:
            return  # Already exists

        if course_group not in self.groups:
            self.groups[course_group] = MockRmsGroup(name=course_group)

        project = MockRmsProject(name=course_public_repo, group=course_group, visibility="public")
        self.projects[project_path] = project
        self.groups[course_group].projects[course_public_repo] = project

    def create_students_group(
        self,
        course_students_group: str,
    ) -> None:
        if course_students_group not in self.groups:
            self.groups[course_students_group] = MockRmsGroup(name=course_students_group)

    def check_project_exists(
        self,
        project_name: str,
        project_group: str,
    ) -> bool:
        project_path = f"{project_group}/{project_name}"
        return project_path in self.projects

    def create_project(
        self,
        rms_user: RmsUser,
        course_students_group: str,
        course_public_repo: str,
    ) -> None:
        project_path = f"{course_students_group}/{rms_user.username}"
        if project_path in self.projects:
            # Add user as member if not already
            if rms_user.id not in self.projects[project_path].members:
                self.projects[project_path].members.append(rms_user.id)
            return

        # Create project if it doesn't exist
        project = MockRmsProject(name=rms_user.username, group=course_students_group, visibility="private")
        project.members.append(rms_user.id)
        self.projects[project_path] = project

        # Add to group
        if course_students_group not in self.groups:
            self.groups[course_students_group] = MockRmsGroup(name=course_students_group)
        self.groups[course_students_group].projects[rms_user.username] = project

    def get_url_for_task_base(self, course_public_repo: str, default_branch: str) -> str:
        return f"{self.base_url}/{course_public_repo}/blob/{default_branch}"

    def get_url_for_repo(
        self,
        username: str,
        course_students_group: str,
    ) -> str:
        return f"{self.base_url}/{course_students_group}/{username}"

    def get_rms_user_by_id(
        self,
        user_id: int,
    ) -> RmsUser:
        if user_id not in self.users:
            raise RmsApiException(f"User with id {user_id} not found")
        return self.users[user_id]

    def get_rms_user_by_username(
        self,
        username: str,
    ) -> RmsUser:
        if username not in self.users_by_username:
            raise RmsApiException(f"User with username {username} not found")
        return self.users_by_username[username]

    def check_user_authenticated_in_rms(
        self,
        oauth: OAuth,
        oauth_access_token: str,
        oauth_refresh_token: str,
    ) -> bool:
        # Mock implementation always returns True
        return True

    def get_authenticated_rms_user(
        self,
        oauth_access_token: str,
    ) -> RmsUser:
        # For testing, return last registered user
        return self.users[self.last_user]
