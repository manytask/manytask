from __future__ import annotations

import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Optional

import gitlab
import gitlab.const
import gitlab.v4.objects
import requests
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import session
from gitlab.exceptions import GitlabAuthenticationError, GitlabCreateError, GitlabGetError
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
        try:
            return self._gitlab.groups.get(group_name)
        except (GitlabGetError, AttributeError):
            logger.debug("Direct group access failed, trying search method")
        
        short_group_name = group_name.split("/")[-1]
        group_name_with_spaces = " / ".join(group_name.split("/"))
        
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

    def get_group_path_by_id(self, group_id: int) -> Optional[str]:
        """Get the full path of a GitLab group by its ID.
        
        Args:
            group_id: GitLab group ID
            
        Returns:
            Full path of the group (e.g., 'hse-namespace/test-course') or None if not found
        """
        try:
            group = self._gitlab.groups.get(group_id)
            return getattr(group, 'full_path', None)
        except GitlabGetError:
            logger.warning("Group with ID %s not found", group_id)
            return None

    def create_public_repo(self, course_group: str, course_public_repo: str) -> None:
        logger.info("Creating public repo course_group=%s repo=%s", course_group, course_public_repo)
        group = self._get_group_by_name(course_group)

        for project in self._gitlab.projects.list(get_all=True, search=course_public_repo):
            if project.path_with_namespace == course_public_repo:
                logger.info("Project %s already exists", course_public_repo)
                return

        project_name = course_public_repo.split("/")[-1]
        
        self._gitlab.projects.create(
            {
                "name": project_name,
                "path": project_name,
                "namespace_id": group.id,
                "visibility": "public",
                "shared_runners_enabled": True,
                "auto_devops_enabled": False,
                "initialize_with_readme": True,
            }
        )
        logger.info("Public repo %s created successfully", course_public_repo)

    def create_students_group(self, course_students_group: str, parent_group_id: int | None = None) -> gitlab.v4.objects.Group | None:
        """Create a students group for a course.
        
        :param course_students_group: Full path to the students group (e.g., "namespace/course/students-2025-fall")
        :param parent_group_id: Optional parent group ID. If provided, creates as subgroup. If None, creates top-level group.
        :return: The created group object, or None if group already exists
        """
        try:
            return self._get_group_by_name(course_students_group)
        except RuntimeError:
            pass
        
        short_name = course_students_group.split("/")[-1]

        group_data = {
            "name": short_name,
            "path": short_name,
            "visibility": "private",
            "lfs_enabled": True,
            "shared_runners_enabled": True,
        }
        
        if parent_group_id:
            group_data["parent_id"] = parent_group_id
        
        try:
            created_group = self._gitlab.groups.create(group_data)
            return self._gitlab.groups.get(created_group.id)
        except GitlabCreateError as e:
            if "already been taken" in str(e) or "already exists" in str(e).lower():
                logger.warning("Group %s already exists (detected during creation). Trying to find it...", course_students_group)
                
                if parent_group_id:
                    try:
                        parent_group = self._gitlab.groups.get(parent_group_id)
                        subgroups = parent_group.subgroups.list(get_all=True)
                        short_name = course_students_group.split("/")[-1]
                        
                        for subgroup in subgroups:
                            if subgroup.name == short_name or subgroup.path == short_name:
                                logger.info("Found existing students group %s through parent subgroups with id=%s", course_students_group, subgroup.id)
                                return self._gitlab.groups.get(subgroup.id)
                    except Exception as subgroup_error:
                        logger.debug("Failed to find group through parent subgroups: %s", str(subgroup_error))
                
                try:
                    return self._get_group_by_name(course_students_group)
                except RuntimeError:
                    logger.error("Group %s should exist but cannot be found. This may indicate a GitLab indexing delay.", course_students_group)
                    raise RuntimeError(f"Group {course_students_group} creation failed: group already exists but cannot be retrieved. Please try again in a moment.")
            raise

    def create_namespace_group(self, name: str, path: str, description: str | None = None) -> int:
        """Create a top-level GitLab group for a namespace.
        
        :param name: Display name of the group
        :param path: URL path/slug for the group
        :param description: Optional description for the group
        :return: GitLab group ID
        :raises: RuntimeError if group with this path already exists
        """
        logger.info("Creating namespace group name=%s path=%s", name, path)
        
        for group in self._gitlab.groups.list(get_all=True, search=path):
            if group.path == path:
                logger.error("Group with path %s already exists", path)
                raise RuntimeError(f"Group with path {path} already exists")
        
        group_data = {
            "name": name,
            "path": path,
            "visibility": "private",
            "lfs_enabled": True,
            "shared_runners_enabled": True,
        }
        
        if description:
            group_data["description"] = description
        
        created_group = self._gitlab.groups.create(group_data)
        logger.info("Namespace group %s created successfully with id=%s", path, created_group.id)
        
        return created_group.id

    def add_user_to_namespace_group(self, gitlab_group_id: int, user_id: int) -> None:
        """Add a user to a GitLab namespace group with Maintainer access.
        
        :param gitlab_group_id: GitLab group ID
        :param user_id: GitLab user ID
        """
        logger.info("Adding user_id=%s to GitLab group id=%s as Maintainer", user_id, gitlab_group_id)
        
        try:
            group = self._gitlab.groups.get(gitlab_group_id)
            
            try:
                existing_member = group.members.get(user_id)
                logger.info(
                    "User id=%s is already a member of group id=%s with access level %s",
                    user_id,
                    gitlab_group_id,
                    existing_member.access_level,
                )
                if existing_member.access_level != gitlab.const.AccessLevel.MAINTAINER:
                    existing_member.access_level = gitlab.const.AccessLevel.MAINTAINER
                    existing_member.save()
                    logger.info("Updated user id=%s access level to Maintainer", user_id)
            except GitlabGetError:
                group.members.create(
                    {
                        "user_id": user_id,
                        "access_level": gitlab.const.AccessLevel.MAINTAINER,
                    }
                )
                logger.info("User id=%s added to GitLab group id=%s as Maintainer", user_id, gitlab_group_id)
                
        except GitlabGetError as e:
            logger.error("Failed to get GitLab group id=%s: %s", gitlab_group_id, str(e))
            raise RuntimeError(f"Failed to get GitLab group {gitlab_group_id}: {str(e)}")

    def remove_user_from_namespace_group(self, gitlab_group_id: int, user_id: int) -> None:
        """Remove a user from a GitLab namespace group.
        
        :param gitlab_group_id: GitLab group ID
        :param user_id: GitLab user ID (rms_id)
        """
        logger.info("Removing user_id=%s from GitLab group id=%s", user_id, gitlab_group_id)
        
        try:
            group = self._gitlab.groups.get(gitlab_group_id)
            
            try:
                group.members.get(user_id)
                group.members.delete(user_id)
                logger.info("User id=%s removed from GitLab group id=%s", user_id, gitlab_group_id)
            except GitlabGetError:
                logger.warning(
                    "User id=%s is not a member of group id=%s, skipping removal",
                    user_id,
                    gitlab_group_id,
                )
                
        except GitlabGetError as e:
            logger.error("Failed to get GitLab group id=%s: %s", gitlab_group_id, str(e))
            raise RuntimeError(f"Failed to get GitLab group {gitlab_group_id}: {str(e)}")
    
    def create_course_group(self, parent_group_id: int, course_name: str, course_slug: str) -> int:
        """Create a GitLab subgroup for a course inside a namespace group.
        
        :param parent_group_id: GitLab ID of the parent namespace group
        :param course_name: Display name for the course
        :param course_slug: URL slug for the course (validated)
        :return: GitLab group ID of the created course group
        :raises: RuntimeError if group creation fails
        """
        logger.info(
            "Creating course group name=%s slug=%s under parent_group_id=%s",
            course_name,
            course_slug,
            parent_group_id,
        )
        
        try:
            group_data = {
                "name": course_slug,
                "path": course_slug,
                "parent_id": parent_group_id,
                "visibility": "private",
                "lfs_enabled": True,
                "shared_runners_enabled": True,
            }
            
            created_group = self._gitlab.groups.create(group_data)
            logger.info(
                "Course group %s created successfully with id=%s under parent_id=%s",
                course_slug,
                created_group.id,
                parent_group_id,
            )
            
            return created_group.id
            
        except Exception as e:
            logger.error(
                "Failed to create course group slug=%s under parent_id=%s: %s",
                course_slug,
                parent_group_id,
                str(e),
            )
            raise RuntimeError(f"Failed to create course group {course_slug}: {str(e)}")
    
    def delete_group(self, group_id: int) -> None:
        """Delete a GitLab group.
        
        :param group_id: GitLab group ID to delete
        """
        logger.info("Deleting GitLab group id=%s", group_id)
        
        try:
            group = self._gitlab.groups.get(group_id)
            group.delete()
            logger.info("GitLab group id=%s deleted successfully", group_id)
        except GitlabGetError as e:
            logger.warning("Failed to delete GitLab group id=%s: %s (may not exist)", group_id, str(e))
        except Exception as e:
            logger.error("Unexpected error deleting GitLab group id=%s: %s", group_id, str(e))

    def delete_project(self, project_id: int) -> None:
        """Delete a GitLab project.
        
        :param project_id: GitLab project ID to delete
        """
        logger.info("Deleting GitLab project id=%s", project_id)
        
        try:
            project = self._gitlab.projects.get(project_id)
            project.delete()
            logger.info("GitLab project id=%s deleted successfully", project_id)
        except GitlabGetError as e:
            logger.warning("Failed to delete GitLab project id=%s: %s (may not exist)", project_id, str(e))
        except Exception as e:
            logger.error("Unexpected error deleting GitLab project id=%s: %s", project_id, str(e))

    def check_project_exists(self, project_name: str, project_group: str) -> bool:
        gitlab_project_path = f"{project_group}/{project_name}"
        logger.info("Checking if project exists path=%s", gitlab_project_path)

        try:
            project = self._gitlab.projects.get(gitlab_project_path)
        except GitlabGetError:
            logger.info("Project does not exist project_name=%s group=%s", project_name, project_group)
            logger.debug("Gitlab error:", exc_info=True)
            return False
        except GitlabAuthenticationError as e:
            logger.error(
                "GitLab authentication error while checking project existence: %s. "
                "Please check GITLAB_ADMIN_TOKEN in .env file.",
                str(e),
                exc_info=True
            )
            raise RmsApiException(f"GitLab authentication failed: {str(e)}") from e

        project_path = project.path_with_namespace
        logger.debug("Found project candidate path=%s", project_path)
        if project_path == gitlab_project_path:
            logger.info("Project exists project_name=%s group=%s", project_name, project_group)
            return True

        logger.info(
            f"Project does not match the expected pattern:\n"
            f"got project candidate path={project_path}\n"
            f"awaited project_name={project_name} group={project_group}"
        )
        return False

    def create_project(self, rms_user: RmsUser, course_students_group: str, course_public_repo: str) -> None:
        logger.info("Creating project for user=%s in group=%s", rms_user.username, course_students_group)
        
        course_group_path = "/".join(course_students_group.split("/")[:-1])
        
        try:
            course_group = self._get_group_by_name(course_group_path)
        except RuntimeError:
            logger.error("Course group %s not found. Cannot create student project.", course_group_path)
            raise RuntimeError(f"Course group {course_group_path} not found. Please ensure the course is properly set up.")
        
        students_group = None
        try:
            students_group = self._get_group_by_name(course_students_group)
        except RuntimeError:
            logger.warning("Students group %s not found. Creating it now...", course_students_group)
            students_group = self.create_students_group(course_students_group, parent_group_id=course_group.id)
            if students_group is None:
                try:
                    students_group = self._get_group_by_name(course_students_group)
                except RuntimeError:
                    logger.error("Failed to retrieve students group %s after creation", course_students_group)
                    raise RuntimeError(f"Failed to create or retrieve students group {course_students_group}. Please try again.")
        
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
                "namespace_id": students_group.id,
                "forking_access_level": "disabled",
                # MR target self main
                "mr_default_target_self": True,
                # Enable shared runners
                # TODO: Relay on groups runners
                # "shared_runners_enabled": students_group.shared_runners_setting == "enabled",
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
            raise RmsApiException(f"No users found for username {username}")

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
        return requests.get(f"{self.base_url}/api/v4/user", headers=headers, verify=self._verify_ssl)

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
