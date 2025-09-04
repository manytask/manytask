from __future__ import annotations

import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import gitlab
import gitlab.const
import gitlab.v4.objects
import requests
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import session
from requests.exceptions import HTTPError

from .abstract import AuthApi, AuthenticatedUser, RmsApi, RmsUser

logger = logging.getLogger(__name__)


class GitLabApiException(Exception):
    pass


@dataclass
class GitLabConfig:
    """Configuration for GitLab API connection and course settings."""

    base_url: str
    admin_token: str
    dry_run: bool = False


class GitLabApi(RmsApi, AuthApi):
    def __init__(
        self,
        config: GitLabConfig,
    ):
        self.dry_run = config.dry_run
        self._base_url = config.base_url
        self._gitlab = gitlab.Gitlab(self.base_url, private_token=config.admin_token)

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
        logger.info(f"Creating new GitLab user username={username} email={email}")
        try:
            name = f"{firstname} {lastname}"
            new_user = self._gitlab.users.create(
                {
                    "email": email,
                    "username": username,
                    "name": name,
                    "external": False,
                    "password": password,
                    "skip_confirmation": True,
                }
            )
            logger.info(f"GitLab user created successfully id={new_user.id} username={username}")
            return RmsUser(id=new_user.id, username=username, name=name)
        except Exception:
            logger.error(f"Failed to create GitLab user username={username} email={email}", exc_info=True)
            raise

    def _get_group_by_name(self, group_name: str) -> gitlab.v4.objects.Group:
        short_group_name = group_name.split("/")[-1]
        group_name_with_spaces = " / ".join(group_name.split("/"))
        logger.debug(f"Searching for group group_name={group_name}")
        try:
            return next(
                group
                for group in self._gitlab.groups.list(get_all=True, search=group_name)
                if group.name == short_group_name and group.full_name == group_name_with_spaces
            )
        except StopIteration:
            raise RuntimeError(f"Unable to find group {group_name}")

    def _get_project_by_name(self, project_name: str) -> gitlab.v4.objects.Project:
        short_project_name = project_name.split("/")[-1]
        logger.debug(f"Searching for project project_name={project_name}")
        try:
            return next(
                project
                for project in self._gitlab.projects.list(get_all=True, search=short_project_name)
                if project.path_with_namespace == project_name
            )
        except StopIteration:
            raise RuntimeError(f"Unable to find project {project_name}")

    def create_public_repo(self, course_group: str, course_public_repo: str) -> None:
        logger.info(f"Creating public repo course_group={course_group} repo={course_public_repo}")
        group = self._get_group_by_name(course_group)
        for project in self._gitlab.projects.list(get_all=True, search=course_public_repo):
            if project.path_with_namespace == course_public_repo:
                logger.info(f"Project {course_public_repo} already exists")
                return
        self._gitlab.projects.create(
            {
                "name": course_public_repo,
                "path": course_public_repo,
                "namespace_id": group.id,
                "visibility": "public",
                "shared_runners_enabled": True,
                "auto_devops_enabled": False,
                "initialize_with_readme": True,
            }
        )
        logger.info(f"Public repo {course_public_repo} created successfully")

    def create_students_group(self, course_students_group: str) -> None:
        logger.info(f"Creating students group name={course_students_group}")
        for group in self._gitlab.groups.list(get_all=True, search=course_students_group):
            if group.name == course_students_group and group.full_name == course_students_group:
                logger.info(f"Group {course_students_group} already exists")
                return
        self._gitlab.groups.create(
            {
                "name": course_students_group,
                "path": course_students_group,
                "visibility": "private",
                "lfs_enabled": True,
                "shared_runners_enabled": True,
            }
        )
        logger.info(f"Students group {course_students_group} created successfully")

    def check_project_exists(self, project_name: str, project_group: str) -> bool:
        gitlab_project_path = f"{project_group}/{project_name}"
        logger.debug(f"Checking if project exists path={gitlab_project_path}")
        for project in self._gitlab.projects.list(get_all=True, search=project_name):
            logger.debug(f"Found project candidate path={project.path_with_namespace}")
            if project.path_with_namespace == gitlab_project_path:
                logger.info(f"Project exists project_name={project_name} group={project_group}")
                return True
        logger.info(f"Project does not exist project_name={project_name} group={project_group}")
        return False

    def create_project(self, rms_user: RmsUser, course_students_group: str, course_public_repo: str) -> None:
        logger.info(f"Creating project for user={rms_user.username} in group={course_students_group}")
        course_group = self._get_group_by_name(course_students_group)
        gitlab_project_path = f"{course_students_group}/{rms_user.username}"
        for project in self._gitlab.projects.list(get_all=True, search=rms_user.username):
            if project.path_with_namespace == gitlab_project_path:
                logger.info(f"Project already exists for user={rms_user.username} group={course_students_group}")
                project = self._gitlab.projects.get(project.id)
                try:
                    project.members.create(
                        {
                            "user_id": rms_user.id,
                            "access_level": gitlab.const.AccessLevel.DEVELOPER,
                        }
                    )
                    logger.info(f"Access granted to existing project user={rms_user.username}")
                except gitlab.GitlabCreateError:
                    logger.warning(f"Access already granted or conflict user={rms_user.username}")
                return

        course_public_project = self._get_project_by_name(course_public_repo)
        logger.debug(f"Forking repo {course_public_project.path_with_namespace} for user={rms_user.username}")
        fork = course_public_project.forks.create(
            {
                "name": rms_user.username,
                "path": rms_user.username,
                "namespace_id": course_group.id,
                "forking_access_level": "disabled",
                "mr_default_target_self": True,
                "ci_config_path": f".gitlab-ci.yml@{course_public_project.path_with_namespace}",
                "merge_method": "squash",
                "auto_devops_enabled": False,
            }
        )
        project = self._gitlab.projects.get(fork.id)
        for protected_branch in project.protectedbranches.list(get_all=True):
            protected_branch.delete()
        project.save()
        logger.info(f"Forked project created for user={rms_user.username} repo={project.path_with_namespace}")
        try:
            project.members.create(
                {
                    "user_id": rms_user.id,
                    "access_level": gitlab.const.AccessLevel.DEVELOPER,
                }
            )
            logger.info(f"Access granted for forked project user={rms_user.username}")
        except gitlab.GitlabCreateError:
            logger.warning(f"Access already granted or conflict on forked project user={rms_user.username}")

    def _construct_rms_user(self, user: dict[str, Any]) -> RmsUser:
        return RmsUser(id=user["id"], username=user["username"], name=user["name"])

    def _get_rms_users_by_username(self, username: str) -> list[RmsUser]:
        logger.debug(f"Searching for users by username={username}")
        users = self._gitlab.users.list(get_all=True, username=username)
        return [self._construct_rms_user(user._attrs) for user in users]

    def get_rms_user_by_id(self, user_id: int) -> RmsUser:
        logger.info(f"Searching for user by id={user_id}")
        user = self._gitlab.users.get(user_id)
        logger.info(f"User found id={user.id} username={user.username}")
        return self._construct_rms_user(user._attrs)

    def get_rms_user_by_username(self, username: str) -> RmsUser:
        logger.info(f"Searching for user by username={username}")
        potential_rms_users = self._get_rms_users_by_username(username)
        potential_rms_users = [rms_user for rms_user in potential_rms_users if rms_user.username == username]
        if len(potential_rms_users) == 0:
            logger.error(f"No users found username={username}")
            raise GitLabApiException(f"No users found for username {username}")

        rms_user = potential_rms_users[0]
        logger.info(f"User found username={rms_user.username}")
        return rms_user

    def get_authenticated_rms_user(self, oauth_access_token: str) -> RmsUser:
        logger.debug("Fetching authenticated RMS user via token")
        response = self._make_auth_request(oauth_access_token)
        response.raise_for_status()
        return self._construct_rms_user(response.json())

    def get_url_for_task_base(self, course_public_repo: str, default_branch: str) -> str:
        return f"{self.base_url}/{course_public_repo}/blob/{default_branch}"

    def get_url_for_repo(
        self,
        username: str,
        course_students_group: str,
    ) -> str:
        return f"{self.base_url}/{course_students_group}/{username}"

    def _make_auth_request(self, token: str) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"}
        return requests.get(f"{self.base_url}/api/v4/user", headers=headers)

    def check_user_is_authenticated(
        self,
        oauth: OAuth,
        oauth_access_token: str,
        oauth_refresh_token: str,
    ) -> bool:
        response = self._make_auth_request(oauth_access_token)

        try:
            response.raise_for_status()
            return True
        except HTTPError as e:
            if e.response.status_code == HTTPStatus.UNAUTHORIZED:
                try:
                    logger.info("Access token expired. Trying to refresh token.")

                    new_tokens = oauth.gitlab.fetch_access_token(
                        grant_type="refresh_token",
                        refresh_token=oauth_refresh_token,
                    )

                    new_access = new_tokens.get("access_token")
                    new_refresh = new_tokens.get("refresh_token", oauth_refresh_token)

                    response = self._make_auth_request(new_access)
                    response.raise_for_status()

                    session["gitlab"].update({"access_token": new_access, "refresh_token": new_refresh})
                    logger.info("Token refreshed successfully.")

                    return True
                except (HTTPError, OAuthError):
                    logger.error("Failed to refresh token", exc_info=True)
                    return False

            logger.info(f"User is not logged to GitLab: {e}", exc_info=True)
            return False

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        logger.debug("Fetching authenticated user via token")
        response = self._make_auth_request(oauth_access_token)
        response.raise_for_status()
        user = response.json()
        logger.info(f"Authenticated user retrieved id={user['id']} username={user['username']}")
        return AuthenticatedUser(id=user["id"], username=user["username"])
