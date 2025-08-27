from __future__ import annotations

import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import requests

from .abstract import RmsApi, RmsUser

logger = logging.getLogger(__name__)


@dataclass
class SourcecraftConfig:
    """Configuration for Sourcecraft API connection and course settings."""

    base_url: str
    api_url: str
    admin_token: str
    org_slug: str
    course_name: str
    dry_run: bool = False


class SourcecraftApi(RmsApi):
    def __init__(
        self,
        config: SourcecraftConfig,
    ):
        """Initialize Sourcecraft API client with configuration.

        :param config: SourcecraftConfig instance containing all necessary settings
        """
        self.dry_run = config.dry_run
        self._base_url = config.base_url
        self._api_url = config.api_url
        self._admin_token = config.admin_token
        self._org_slug = config.org_slug
        # self._course_name = config.course_name
        # Initialize any additional Sourcecraft-specific components here
        logger.info(f"Initializing SourcecraftApi with base_url: {self.base_url}")

    def _create_template_repo(self, repo_slug: str) -> None:
        """This method triggers SourceCraft CI, so creation is actually async and
        returned json is an operation which caller can poll to check if creation is finished.
        """
        url = f"{self._api_url}/{self._org_slug}/{repo_slug}/ci_workflows/upsert-template-repo-workflow/trigger"
        headers = {
            "Authorization": f"Bearer {self._admin_token}",
            "Content-Type": "application/json",
        }
        data: dict[str, Any] = {}
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    # TODO: seems unused, remove?
    def create_public_repo(
        self,
        course_group: str,
        course_public_repo: str,
    ) -> None:
        """Create a public repository for course materials.

        :param course_group: actually a course name
        :param course_public_repo: UNUSED
        """
        logger.info(f"Creating public repo: {course_group}-template")
        self._create_template_repo(f"{course_group}-template")

    # TODO: seems unused, remove?
    def create_students_group(
        self,
        course_students_group: str,
    ) -> None:
        """Do nothing.

        :param course_students_group: UNUSED
        """
        logger.info("Will skip students group creation, SourceCraft doesn't have user groups yet")

    def check_project_exists(
        self,
        project_name: str,
        destination: str,
    ) -> bool:
        """Check if a project exists in the given group.

        :param project_name: Username of a student
        :param destination: Course name
        :return: True if project exists, False otherwise
        """
        url = f"{self._api_url}/repos/{self._org_slug}/{destination}-{project_name}"
        headers = {
            "Authorization": f"Bearer {self._admin_token}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)

        if response.status_code == HTTPStatus.OK:
            return True
        elif response.status_code == HTTPStatus.NOT_FOUND:
            return False
        else:
            response.raise_for_status()
            return False

    def _create_student_repo(self, course_name: str, login: str) -> None:
        """This method triggers SourceCraft CI, so creation is actually async and
        returned json is an operation which caller can poll to check if creation is finished.
        """
        url = f"{self._api_url}/{self._org_slug}/{course_name}/ci_workflows/upsert-student-repo-workflow/trigger"
        headers = {
            "Authorization": f"Bearer {self._admin_token}",
            "Content-Type": "application/json",
        }
        data: dict[str, Any] = {"inputs": {"login": login}}
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def create_project(
        self,
        rms_user: RmsUser,
        destination: str,
        template: str,
    ) -> None:
        """Create a personal repo for a student.

        :param rms_user: User information
        :param destination: Course name
        :param template: UNUSED, repo will be created from main course repo
        """
        logger.info(f"Creating repo for user {rms_user.username}")
        self._create_student_repo(destination, rms_user.username)

    def get_url_for_task_base(self, template: str, default_branch: str) -> str:
        """Get URL for task base directory in the public repository.

        :param template: Slug of the public course repository
        :param default_branch: Default branch name
        :return: URL to the task base directory
        """
        return f"{self._base_url}/{self._org_slug}/{template}?ref={default_branch}"

    def get_url_for_repo(
        self,
        username: str,
        destination: str,
    ) -> str:
        """Get URL for a student's repository.

        :param username: Student's username
        :param course_students_group: Actually a course name
        :return: URL to the student's repository
        """
        return f"{self._base_url}/{self._org_slug}/{destination}-{username}"

    def register_new_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
    ) -> None:
        """Register a new user in Sourcecraft.

        :param username: User's username
        :param firstname: User's first name
        :param lastname: User's last name
        :param email: User's email address
        :param password: User's password
        """
        logger.info(f"Creating user (username={username})")
        raise NotImplementedError("register_new_user method not implemented yet")

    def get_rms_user_by_id(
        self,
        user_id: int,
    ) -> RmsUser:
        """Get user information by user ID.

        :param user_id: User's ID
        :return: RmsUser object with user information
        """
        logger.info(f"Searching user by ID: {user_id}")
        raise NotImplementedError("get_rms_user_by_id method not implemented yet")

    def get_rms_user_by_username(
        self,
        username: str,
    ) -> RmsUser:
        """Get user information by username.

        :param username: User's username
        :return: RmsUser object with user information
        """
        logger.info(f"Searching user by username: {username}")
        raise NotImplementedError("get_rms_user_by_username method not implemented yet")

    def get_authenticated_rms_user(
        self,
        oauth_access_token: str,
    ) -> RmsUser:
        """Get authenticated user information using OAuth access token.

        :param oauth_access_token: OAuth access token
        :return: RmsUser object with user information
        """
        logger.info("Getting authenticated user from OAuth token")
        raise NotImplementedError("get_authenticated_rms_user method not implemented yet")

    def _construct_rms_user(self, user_data: dict[str, Any]) -> RmsUser:
        """Construct RmsUser object from API response data.

        :param user_data: User data from API response
        :return: RmsUser object
        """
        logger.info("Constructing RmsUser from API data")
        raise NotImplementedError("_construct_rms_user method not implemented yet")
