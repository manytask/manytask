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

from .abstract import AuthApi, AuthenticatedUser, RmsApi, RmsApiException, RmsUser

logger = logging.getLogger(__name__)


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
        """Initialize GitLab API client with configuration.

        :param config: GitLabConfig instance containing all necessary settings
        """
        self.dry_run = config.dry_run
        self._base_url = config.base_url
        self._gitlab = gitlab.Gitlab(self.base_url, private_token=config.admin_token)

    def register_new_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
    ) -> RmsUser:
        logger.info("Creating new GitLab user username=%s email=%s", username, email)
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
            logger.info("GitLab user created successfully id=%s username=%s", new_user.id, username)
            return RmsUser(id=new_user.id, username=username, name=name)
        except Exception:
            logger.error("Failed to create GitLab user username=%s email=%s", username, email, exc_info=True)
            raise

    def _get_group_by_name(self, group_name: str) -> gitlab.v4.objects.Group:
        short_group_name = group_name.split("/")[-1]
        group_name_with_spaces = " / ".join(group_name.split("/"))
        logger.debug("Searching for group group_name=%s", group_name)
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
        logger.debug("Searching for project project_name=%s", project_name)
        try:
            return next(
                project
                for project in self._gitlab.projects.list(get_all=True, search=short_project_name)
                if project.path_with_namespace == project_name
            )
        except StopIteration:
            raise RuntimeError(f"Unable to find project {project_name}")

    def create_public_repo(self, course_group: str, course_public_repo: str) -> None:
        logger.info("Creating public repo course_group=%s repo=%s", course_group, course_public_repo)
        group = self._get_group_by_name(course_group)

        for project in self._gitlab.projects.list(get_all=True, search=course_public_repo):
            if project.path_with_namespace == course_public_repo:
                logger.info("Project %s already exists", course_public_repo)
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
        logger.info("Public repo %s created successfully", course_public_repo)

    def create_students_group(self, course_students_group: str) -> None:
        logger.info("Creating students group name=%s", course_students_group)
        for group in self._gitlab.groups.list(get_all=True, search=course_students_group):
            if group.name == course_students_group and group.full_name == course_students_group:
                logger.info("Group %s already exists", course_students_group)
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
        logger.info("Students group %s created successfully", course_students_group)

    def check_project_exists(self, project_name: str, project_group: str) -> bool:
        gitlab_project_path = f"{project_group}/{project_name}"
        logger.info("Checking if project exists path=%s", gitlab_project_path)

        projects = self._gitlab.projects.list(get_all=False, search=gitlab_project_path)

        if len(projects) == 0:
            logger.info("Project does not exist project_name=%s group=%s", project_name, project_group)
            return False

        logger.debug("Found project candidate path=%s", projects[0].path_with_namespace)
        if projects[0].path_with_namespace == gitlab_project_path:
            logger.info("Project exists project_name=%s group=%s", project_name, project_group)
            return True

        logger.info(
            f"Project does not match the expected pattern:\n"
            f"got project candidate path={projects[0].path_with_namespace}\n"
            f"awaited project_name={project_name} group={project_group}"
        )
        return False

    def create_project(self, rms_user: RmsUser, course_students_group: str, course_public_repo: str) -> None:
        logger.info("Creating project for user=%s in group=%s", rms_user.username, course_students_group)
        course_group = self._get_group_by_name(course_students_group)

        gitlab_project_path = f"{course_students_group}/{rms_user.username}"
        logger.info("Gitlab project path: %s", gitlab_project_path)

        for project in self._gitlab.projects.list(get_all=True, search=rms_user.username):
            # Because of implicit conversion
            # TODO: make global problem solve
            if project.path_with_namespace == gitlab_project_path:
                logger.info("Project already exists for user=%s group=%s", rms_user.username, course_students_group)
                project = self._gitlab.projects.get(project.id)
                try:
                    # ensure user is a member of the project
                    member = project.members.create(
                        {
                            "user_id": rms_user.id,
                            "access_level": gitlab.const.AccessLevel.DEVELOPER,
                        }
                    )
                    logger.info("Access granted to existing project user=%s", member)
                except gitlab.GitlabCreateError:
                    logger.warning("Access already granted or conflict user=%s", rms_user.username)

                return

        course_public_project = self._get_project_by_name(course_public_repo)
        logger.debug("Forking repo %s for user=%s", course_public_project.path_with_namespace, rms_user.username)
        fork = course_public_project.forks.create(
            {
                "name": rms_user.username,
                "path": rms_user.username,
                "namespace_id": course_group.id,
                "forking_access_level": "disabled",
                # MR target self main
                "mr_default_target_self": True,
                # Enable shared runners
                # TODO: Relay on groups runners
                # "shared_runners_enabled": course_group.shared_runners_setting == "enabled",
                # Set external gitlab-ci config from public repo
                "ci_config_path": f".gitlab-ci.yml@{course_public_project.path_with_namespace}",
                # Merge method to squash
                "merge_method": "squash",
                # Disable AutoDevOps
                "auto_devops_enabled": False,
            }
        )
        project = self._gitlab.projects.get(fork.id)
        # TODO: think .evn config value
        # Unprotect all branches
        for protected_branch in project.protectedbranches.list(get_all=True):
            protected_branch.delete()
        project.save()

        logger.info("Forked project created for user=%s repo=%s", rms_user.username, project.path_with_namespace)
        try:
            member = project.members.create(
                {
                    "user_id": rms_user.id,
                    "access_level": gitlab.const.AccessLevel.DEVELOPER,
                }
            )
            logger.info("Access granted for forked project user=%s", member.username)
        except gitlab.GitlabCreateError:
            logger.warning("Access already granted or conflict on forked project user=%s", rms_user.username)

    def _construct_rms_user(
        self,
        user: dict[str, Any],
    ) -> RmsUser:
        return RmsUser(
            id=user["id"],
            username=user["username"],
            name=user["name"],
        )

    def _get_rms_users_by_username(
        self,
        username: str,
    ) -> list[RmsUser]:
        logger.debug("Searching for users by username=%s", username)
        users = self._gitlab.users.list(get_all=True, username=username)
        return [self._construct_rms_user(user._attrs) for user in users]

    def get_rms_user_by_id(
        self,
        user_id: int,
    ) -> RmsUser:
        logger.info("Searching for user by id=%s", user_id)
        user = self._gitlab.users.get(user_id)
        logger.info("User found id=%s username=%s", user.id, user.username)
        return self._construct_rms_user(user._attrs)

    def get_rms_user_by_username(
        self,
        username: str,
    ) -> RmsUser:
        logger.info("Searching for user by username=%s", username)
        potential_rms_users = self._get_rms_users_by_username(username)
        potential_rms_users = [rms_user for rms_user in potential_rms_users if rms_user.username == username]
        if len(potential_rms_users) == 0:
            logger.error("No users found username=%s", username)
            raise GitLabApiException(f"No users found for username {username}")

        rms_user = potential_rms_users[0]
        logger.info("User found username=%s", rms_user.username)
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

            logger.info("User is not logged to GitLab: %s", e, exc_info=True)
            return False

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        logger.debug("Fetching authenticated user via token")
        response = self._make_auth_request(oauth_access_token)
        response.raise_for_status()
        user = response.json()
        logger.info("Authenticated user retrieved id=%s username=%s", user["id"], user["username"])
        return AuthenticatedUser(id=user["id"], username=user["username"])
