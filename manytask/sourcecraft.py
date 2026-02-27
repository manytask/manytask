from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any

import httpx

from .abstract import RmsApi, RmsApiException, RmsUser

logger = logging.getLogger(__name__)


@dataclass
class SourceCraftConfig:
    """Configuration for Sourcecraft API connection and course settings."""

    base_url: str
    api_url: str
    admin_token: str
    org_slug: str
    iam_api_url: str = "https://iam.api.cloud.yandex.net/iam/v1"
    dry_run: bool = False


class SourceCraftApi(RmsApi):
    def __init__(
        self,
        config: SourceCraftConfig,
    ):
        """Initialize Sourcecraft API client with configuration.

        :param config: SourcecraftConfig instance containing all necessary settings
        """
        self.dry_run = config.dry_run
        self._base_url = config.base_url
        self._admin_token = config.admin_token
        self._org_slug = config.org_slug

        self._client = httpx.Client(
            base_url=config.api_url,
        )
        self._iam_client = httpx.Client(
            base_url=config.iam_api_url,
        )

        self._iam_token: str | None = None
        self._iam_token_last_issued: datetime | None = None

        logger.info(f"Initializing SourcecraftApi with base_url: {self.base_url}")

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        kwargs.setdefault("headers", {}).update(self._request_headers)
        return self._client.request(method, path, **kwargs)

    @property
    def iam_token(self) -> str:
        if (
            self._iam_token is None
            or self._iam_token_last_issued is None
            or self._iam_token_last_issued < datetime.now() - timedelta(hours=1)
        ):
            self._iam_token = self._get_iam_token()
            self._iam_token_last_issued = datetime.now()
        return self._iam_token

    def _get_iam_token(self) -> str:
        response = self._iam_client.post(
            "tokens",
            json={
                "yandexPassportOauthToken": self._admin_token,
            },
        )
        if response.status_code != HTTPStatus.OK:
            raise RmsApiException(f"Failed to get IAM token: {response.text}")
        return response.json()["iamToken"]

    @property
    def _request_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.iam_token}",
            "Content-Type": "application/json",
        }

    def _get_repo(
        self,
        repo_slug: str,
    ) -> httpx.Response:
        return self._request("GET", f"{self._org_slug}/{repo_slug}")

    def _create_repo(self, repo_slug: str, visibility: str, template_id: int | None = None) -> httpx.Response:
        payload: dict[str, Any] = {
            "name": repo_slug,
            "slug": repo_slug,
            "visibility": visibility,
        }
        if template_id is not None:
            payload["templating_options"] = {
                "template_id": template_id,
            }
        return self._request("POST", f"orgs/{self._org_slug}/repos", json=payload)

    def _update_repo(
        self,
        repo_slug: str,
        data: dict[str, Any],
    ) -> httpx.Response:
        return self._request("PATCH", f"{self._org_slug}/{repo_slug}", json=data)

    def _add_repo_role(
        self,
        repo_slug: str,
        role: str,
        user_id: str,
    ) -> httpx.Response:
        payload: dict[str, Any] = {
            "subject_roles": [
                {
                    "role": role,
                    "subject": {
                        "type": "user",
                        "id": user_id,
                    },
                }
            ]
        }
        return self._request("POST", f"{self._org_slug}/{repo_slug}/roles", json=payload)

    # Comment for this and all further methods with "course_group", "course_public_repo" and
    # "course_students_group" parameters:
    #   - course_group is expected to be in format "namespace/course_group"
    #   - course_public_repo is expected to be in format "namespace/course_group/public_repo"
    #   - course_students_group is expected to be in format "namespace/course_group/students_group".
    # In GitLab, expected course structure is smth like "namespace/course_group/public_repo" for public
    # repo and "namespace/course_group/students_group/student_repo" for student repos. But in SourceCraft,
    # there is no groups, so expected structure is "organization/course_name-repo_name" for all repos.
    # That limitation is the main reason for that split('/')[-1] parts all over the place.
    def create_public_repo(
        self,
        course_group: str,
        course_public_repo: str,
    ) -> None:
        """Create a public repository for course materials.

        :param course_group: strig in form of "namespace/course_group"
        :param course_public_repo: string in form of "namespace/course_group/public_repo"
        """

        course_public_repo = course_public_repo.split("/")[-1]
        course_group = course_group.split("/")[-1]

        repo_slug = f"{course_group}-{course_public_repo}"

        logger.info(f"Creating public repo: {repo_slug}")

        response = self._create_repo(
            repo_slug=repo_slug,
            visibility="public",
            template_id=None,
        )
        if response.status_code != HTTPStatus.CREATED:
            raise RmsApiException(f"Failed to create repo: {response.json()}")

        data: dict[str, Any] = {"template_type": "organizational"}
        response = self._update_repo(repo_slug, data)
        if response.status_code != HTTPStatus.OK:
            raise RmsApiException(f"Failed to create repo: {response.json()}")

    def create_students_group(
        self,
        course_students_group: str,
        parent_group_id: int | None = None,
    ) -> None:
        """Do nothing.

        :param course_students_group: UNUSED
        """
        logger.info("Will skip students group creation, SourceCraft doesn't have user groups yet")

    # WARN: it is expected that project_group is smth like "namespace/course_group/students_group"
    # because that is the only way this method is used right now.
    def check_project_exists(
        self,
        project_name: str,
        project_group: str,
    ) -> bool:
        """Check if a project exists in the given group.

        :param project_name: repo slug
        :param project_group: string in form of "namespace/course_group/students_group"
        :return: True if repo exists, False otherwise
        """
        group = project_group.split("/")[-2]
        response = self._get_repo(f"{group}-{project_name}")

        if response.status_code == HTTPStatus.OK:
            return True
        elif response.status_code == HTTPStatus.NOT_FOUND:
            logger.info(f"Project {group}-{project_name} not found")
            return False
        else:
            raise RmsApiException(f"Failed to check if project exists: {response.json()}")

    # TODO: use or remove
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

    def create_project(
        self,
        rms_user: RmsUser,
        course_students_group: str,
        course_public_repo: str,
    ) -> None:
        """Create a personal repo for a student.

        :param rms_user: User information
        :param course_students_group: string in form of "namespace/course_group/students_group"
        :param course_public_repo: string in form of "namespace/course_group/public_repo"
        """
        logger.info(f"Creating repo for user {rms_user.username}")

        course_public_repo = course_public_repo.split("/")[-1]
        group = course_students_group.split("/")[-2]
        public_repo_slug = f"{group}-{course_public_repo}"
        student_repo_slug = f"{group}-{rms_user.username}"

        response = self._get_repo(public_repo_slug)
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise RmsApiException(f"Project {public_repo_slug} not found")
        elif response.status_code != HTTPStatus.OK:
            raise RmsApiException(f"Failed to get project: {response.json()}")

        response = self._create_repo(
            repo_slug=student_repo_slug,
            visibility="private",
            template_id=response.json()["id"],
        )
        if response.status_code != HTTPStatus.CREATED:
            raise RmsApiException(f"Failed to create repo: {response.json()}")

        response = self._add_repo_role(student_repo_slug, "developer", rms_user.id)
        if response.status_code != HTTPStatus.OK:
            raise RmsApiException(f"Failed to add repo role: {response.json()}")

    def get_url_for_task_base(self, course_public_repo: str, default_branch: str) -> str:
        """Get URL for task base directory in the public repository.

        :param course_public_repo: Slug of the public course repository
        :param default_branch: Default branch name
        :return: URL to the task base directory
        """
        # course_public_repo will be in format "group/repo", we need "group-repo" as a repo slug
        parts = course_public_repo.split("/")
        group = parts[-2]
        repo_slug = parts[-1]
        return f"{self._base_url}/{self._org_slug}/{group}-{repo_slug}?ref={default_branch}"

    def get_url_for_repo(
        self,
        username: str,
        course_students_group: str,
    ) -> str:
        """Get URL for a student's repository.

        :param username: Student's username
        :param course_students_group: string in form of "namespace/course_group/students_group"
        :return: URL to the student's repository
        """
        group = course_students_group.split("/")[-2]
        return f"{self._base_url}/{self._org_slug}/{group}-{username}"

    def register_new_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
    ) -> RmsUser:
        raise NotImplementedError("register_new_user method not implemented yet")

    def get_rms_user_by_id(
        self,
        user_id: str,
    ) -> RmsUser:
        return self._get_user_profile(f"id:{user_id}")

    def get_rms_user_by_username(
        self,
        username: str,
    ) -> RmsUser:
        # NOTE: yandex login is expected as username for now
        return self._get_user_by_yandex_login(username)

    def _get_user_by_yandex_login(self, auth_username: str) -> RmsUser:
        cloud_id = self._get_cloud_id_by_yandex_login(auth_username)
        return self._get_user_profile(f"cloud-id:{cloud_id}")

    def _get_cloud_id_by_yandex_login(self, yandex_login: str) -> str:
        response = self._iam_client.get(
            "yandexPassportUserAccounts:byLogin",
            params={"login": yandex_login},
            headers=self._request_headers,
        )
        if response.status_code != HTTPStatus.OK:
            raise RmsApiException(f"Failed to get cloud id by yandex login: {response.json()}")
        return response.json()["id"]

    def _get_user_profile(self, identity: str) -> RmsUser:
        response = self._request("GET", f"users/{identity}")
        if response.status_code != HTTPStatus.OK:
            raise RmsApiException(f"Failed to get cloud id by yandex login: {response.json()}")
        return self._unmarshal_user_profile(response.json())

    def _unmarshal_user_profile(self, data: dict[str, Any]) -> RmsUser:
        return RmsUser(
            id=data["id"],
            username=data["username"],
            name=data["display_name"],
        )

    def create_namespace_group(
        self,
        name: str,
        path: str,
        description: str | None = None,
    ) -> int:
        """Do nothing. "Namespace" in SourceCraft is a Yandex.Cloud organization, we cannot create it via API.
        :return: -1
        TODO: check that org exists and return its UUID
        """
        return -1

    def add_user_to_namespace_group(
        self,
        gitlab_group_id: int,
        user_rms_id: str,
    ) -> None:
        # TODO: invite user to org?
        return None

    def remove_user_from_namespace_group(
        self,
        gitlab_group_id: int,
        user_rms_id: str,
    ) -> None:
        raise NotImplementedError("remove_user_from_namespace_group method not implemented yet")

    def create_course_group(
        self,
        parent_group_id: int | None,
        course_name: str,
        course_slug: str,
    ) -> int:
        # TODO: implement when SourceCraft supports groups of repos
        return -1

    def delete_group(self, group_id: int) -> None:
        raise NotImplementedError("delete_group method not implemented yet")

    def delete_project(self, project_id: int) -> None:
        raise NotImplementedError("delete_project method not implemented yet")

    def get_group_path_by_id(self, group_id: int) -> str | None:
        raise NotImplementedError("get_group_path_by_id method not implemented yet")
