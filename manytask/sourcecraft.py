from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import requests

from .abstract import RmsApi, RmsUser, StorageApi, StoredUser

logger = logging.getLogger(__name__)


@dataclass
class SourceCraftConfig:
    """Configuration for Sourcecraft API connection and course settings."""

    base_url: str
    api_url: str
    admin_token: str
    org_slug: str
    dry_run: bool = False


class SourceCraftApi(RmsApi):
    def __init__(
        self,
        config: SourceCraftConfig,
        storage_api: StorageApi,
    ):
        """Initialize Sourcecraft API client with configuration.

        :param config: SourcecraftConfig instance containing all necessary settings
        """
        self._storage_api: StorageApi = storage_api
        self.dry_run = config.dry_run
        self._base_url = config.base_url
        self._api_url = config.api_url
        self._admin_token = config.admin_token
        self._org_slug = config.org_slug
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
        url = f"{self._api_url}/repos/{self._org_slug}/{destination}-{self._normalize_string(project_name)}"
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

    def _normalize_string(self, text: str) -> str:
        """Normalize string by applying multiple transformation rules.

        Rules applied:
        1. Convert all letters to lowercase
        2. Replace [\\s_.@]+ with '-'
        3. Remove all characters not matching [A-Za-z0-9\\-]
        4. Replace multiple consecutive dashes with single dash
        5. Strip leading and trailing dashes

        :param text: Input string to normalize
        :return: Normalized string suitable for use as slug
        """
        # 1. Convert to lowercase
        result = text.lower()

        # 2. Replace spaces, underscores, dots, @ with dashes
        result = re.sub(r"[\s_.@]+", "-", result)

        # 3. Remove all characters not matching [A-Za-z0-9\-]
        result = re.sub(r"[^A-Za-z0-9\-]+", "", result)

        # 4. Replace multiple consecutive dashes with single dash
        result = re.sub(r"-{2,}", "-", result)

        # 5. Strip leading and trailing dashes
        result = result.strip("-")

        return result

    def _create_student_repo(self, course_name: str, login: str) -> None:
        """This method triggers SourceCraft CI, so creation is actually async and
        returned json is an operation which caller can poll to check if creation is finished.
        """
        slug = self._normalize_string(login)
        url = f"{self._api_url}/{self._org_slug}/{course_name}/ci_workflows/upsert-student-repo-workflow/trigger"
        headers = {
            "Authorization": f"Bearer {self._admin_token}",
            "Content-Type": "application/json",
        }
        data: dict[str, Any] = {
            "input": {
                "values": [
                    {"name": "student-login", "value": slug},
                    {"name": "student-email", "value": f"{login}@yandex.ru"},
                ]
            }
        }
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def create_project(
        self,
        rms_user: RmsUser,
        destination: str,
        public_repo: str,
    ) -> None:
        """Create a personal repo for a student.

        :param rms_user: User information
        :param destination: Course name
        :param template: UNUSED, repo will be created from main course repo
        """
        logger.info(f"Creating repo for user {rms_user.username}")
        self._create_student_repo(destination, rms_user.username)

    def get_url_for_task_base(self, public_repo: str, default_branch: str) -> str:
        """Get URL for task base directory in the public repository.

        :param public_repo: Slug of the public course repository
        :param default_branch: Default branch name
        :return: URL to the task base directory
        """
        return f"{self._base_url}/{self._org_slug}/{public_repo}?ref={default_branch}"

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
        return f"{self._base_url}/{self._org_slug}/{destination}-{self._normalize_string(username)}"

    def register_new_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
    ) -> None:
        # do nothing
        return None

    def get_rms_user_by_id(
        self,
        user_id: int,
    ) -> RmsUser:
        storedUser: StoredUser = self._storage_api.get_stored_user_by_id(user_id)
        return storedUser.rms_identity

    def get_rms_user_by_username(
        self,
        username: str,
    ) -> RmsUser:
        storedUser: StoredUser = self._storage_api.get_stored_user(username)
        return storedUser.rms_identity

    # TODO: seems unused, remove?
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
