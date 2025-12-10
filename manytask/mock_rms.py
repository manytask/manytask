from dataclasses import dataclass, field
from typing import Any, Dict, List

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
    members: List[int] = field(default_factory=list)


class MockRmsApi(RmsApi):
    def __init__(self, base_url: str):
        self._base_url = base_url
        self.users: Dict[int, RmsUser] = {}
        self.users_by_username: Dict[str, RmsUser] = {}
        self.groups: Dict[str, MockRmsGroup] = {}
        self.projects: Dict[str, MockRmsProject] = {}  # key: "group/project"
        self.namespace_groups: Dict[str, int] = {}  # path -> group_id
        self.last_user: int = -1
        self.register_new_user("instance_admin", "Admin", "Adminov", "mail@spam.com", "qwerty")
        self.last_group_id: int = 0

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
        parent_group_id: int | None = None,
    ) -> Any:
        if course_students_group not in self.groups:
            self.groups[course_students_group] = MockRmsGroup(name=course_students_group)
        return self.groups[course_students_group]

    def create_namespace_group(
        self,
        name: str,
        path: str,
        description: str | None = None,
    ) -> int:
        if path in self.namespace_groups:
            raise RuntimeError(f"Group with path {path} already exists")
        
        self.last_group_id += 1
        group_id = self.last_group_id
        self.namespace_groups[path] = group_id
        self.groups[path] = MockRmsGroup(name=name)
        
        return group_id

    def add_user_to_namespace_group(self, gitlab_group_id: int, user_id: int) -> None:
        """Add a user to a namespace group (mock implementation).
        
        :param gitlab_group_id: GitLab group ID
        :param user_id: User ID to add
        """
        group_path = None
        for path, gid in self.namespace_groups.items():
            if gid == gitlab_group_id:
                group_path = path
                break
        
        if group_path is None:
            raise RuntimeError(f"Group with id {gitlab_group_id} not found")
        
        if user_id not in self.groups[group_path].members:
            self.groups[group_path].members.append(user_id)

    def remove_user_from_namespace_group(self, gitlab_group_id: int, user_id: int) -> None:
        """Remove a user from a namespace group (mock implementation).
        
        :param gitlab_group_id: GitLab group ID
        :param user_id: User ID to remove
        """
        group_path = None
        for path, gid in self.namespace_groups.items():
            if gid == gitlab_group_id:
                group_path = path
                break
        
        if group_path is None:
            raise RuntimeError(f"Group with id {gitlab_group_id} not found")
        
        if user_id in self.groups[group_path].members:
            self.groups[group_path].members.remove(user_id)

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
    
    def create_course_group(
        self,
        parent_group_id: int,
        course_name: str,
        course_slug: str,
    ) -> int:
        """Create a course subgroup under a namespace group (mock implementation).
        
        :param parent_group_id: ID of parent namespace group
        :param course_name: Display name for the course
        :param course_slug: URL slug for the course
        :return: Created group ID
        """
        parent_path = None
        for path, gid in self.namespace_groups.items():
            if gid == parent_group_id:
                parent_path = path
                break
        
        if parent_path is None:
            raise RuntimeError(f"Parent group with id {parent_group_id} not found")
        
        course_group_path = f"{parent_path}/{course_slug}"
        
        if course_group_path in self.namespace_groups:
            raise RuntimeError(f"Course group with path {course_group_path} already exists")
        
        self.last_group_id += 1
        group_id = self.last_group_id
        self.namespace_groups[course_group_path] = group_id
        self.groups[course_group_path] = MockRmsGroup(name=course_slug)
        
        return group_id
    
    def delete_group(self, group_id: int) -> None:
        """Delete a group (mock implementation).
        
        :param group_id: Group ID to delete
        """
        group_path = None
        for path, gid in self.namespace_groups.items():
            if gid == group_id:
                group_path = path
                break
        
        if group_path:
            del self.namespace_groups[group_path]
            if group_path in self.groups:
                del self.groups[group_path]
    
    def delete_project(self, project_id: int) -> None:
        """Delete a project (mock implementation).
        
        In the mock, we use project paths as keys, so we'll need to track
        project IDs separately. For simplicity, we'll just not raise an error.
        
        :param project_id: Project ID to delete
        """
        pass
    
    def get_group_path_by_id(self, group_id: int) -> str | None:
        """Get the full path of a GitLab group by its ID (mock implementation).
        
        :param group_id: GitLab group ID
        :return: Full path of the group or None if not found
        """
        for path, gid in self.namespace_groups.items():
            if gid == group_id:
                return path
        return None