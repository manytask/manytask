from __future__ import annotations

import logging
from dataclasses import dataclass, field

import gitlab
import gitlab.v4.objects
import requests


logger = logging.getLogger(__name__)


@dataclass
class User:
    username: str
    firstname: str
    lastname: str
    email: str
    password: str

    def __repr__(self) -> str:
        return f'User(username={self.username})'


@dataclass
class Student:
    id: int
    username: str
    name: str
    course_admin: bool = False
    repo: str | None = field(default=None)

    def __repr__(self) -> str:
        return f'Student(username={self.username})'


class GitLabApiException(Exception):
    pass


class GitLabApi:
    def __init__(
            self,
            base_url: str,
            admin_token: str,
            course_private_repo: str,
            course_public_repo: str,
            course_students_group: str,
            *,
            dry_run: bool = False,
    ):
        """
        :param base_url:
        :param admin_token:
        :param course_private_repo:
        :param course_public_repo:
        :param course_students_group:
        """
        self.dry_run = dry_run

        self._url = base_url
        self._gitlab = gitlab.Gitlab(self._url, private_token=admin_token)

        self._course_private_repo = course_private_repo
        self._course_public_repo = course_public_repo
        self._course_group = course_students_group

    def register_new_user(
            self,
            user: User,
    ) -> gitlab.v4.objects.User:
        """
        :param user:
        :return: returns this thing
        https://python-gitlab.readthedocs.io/en/stable/api/gitlab.v4.html#gitlab.v4.objects.User
        but the docs do not really help much. Grep the logs
        """

        logger.info(f'Creating user: {user}')
        # was invented to distinguish between different groups of users automatically by secret
        new_user = self._gitlab.users.create({
            'email': user.email,
            'username': user.username,
            'name': user.firstname + ' ' + user.lastname,
            'external': False,
            'password': user.password,
            'skip_confirmation': True
        })
        logger.info(f'Gitlab user created {new_user}')

        return new_user

    def create_project(
            self,
            student: Student,
    ) -> None:
        try:
            course_group = next(
                group for group in self._gitlab.groups.list(search=self._course_group)
                if group.name == self._course_group
            )
        except StopIteration:
            raise ValueError(f'Gitlab group {self._course_group} not found')

        gitlab_project_path = f'{self._course_group}/{student.username}'
        logger.info(f'Gitlab project path: {gitlab_project_path}')

        for project in self._gitlab.projects.list(search=student.username):
            logger.info(f'Check project path: {project.path_with_namespace}')

            # Because of implicit conversion
            # TODO: make global problem solve
            if project.path_with_namespace == gitlab_project_path:
                logger.info(f'Project {student.username} for group {self._course_group} already exists')
                return

        logger.info(f'Student username {student.username}')
        logger.info(f'Course group {course_group.name}')

        course_public_project = self._gitlab.projects.get(self._course_public_repo)
        fork = course_public_project.forks.create({
            'name': student.username,
            'path': student.username,
            'namespace': course_group.id
        })
        project = self._gitlab.projects.get(fork.id)
        project.shared_runners_enabled = True
        project.ci_config_path = ''
        project.save()

        logger.info(f'Git project forked {course_public_project.path_with_namespace} -> {project.path_with_namespace}')

        try:
            member = project.members.create({
                'user_id': student.id,
                'access_level': gitlab.MAINTAINER_ACCESS,
            })
            logger.info(f'Access to fork granted for {member.username}')
        except gitlab.GitlabCreateError:
            logger.info(f'Access already granted for {student.username}')

    def _parse_user_to_student(
            self,
            user: dict,
    ) -> Student:
        return Student(
            id=user['id'],
            username=user['username'],
            name=user['name'],
            repo=self.get_url_for_repo(user['username'])
        )

    def get_students_by_username(
            self,
            username: str,
    ) -> list[Student]:
        users = self._gitlab.users.list(username=username)
        return [self._parse_user_to_student(user._attrs) for user in users]

    def get_student(
            self,
            user_id: int,
    ) -> Student:
        logger.info(f'Searching user {user_id}...')
        user = self._gitlab.users.get(user_id)
        logger.info(f'User found: "{user.username}"')
        return self._parse_user_to_student(user._attrs)

    def get_authenticated_student(
            self,
            oauth_token: str,
    ) -> Student:
        headers = {'Authorization': 'Bearer ' + oauth_token}
        response = requests.get(f'{self._url}/api/v4/user', headers=headers)
        response.raise_for_status()
        return self._parse_user_to_student(response.json())

    def get_url_for_task_base(self) -> str:
        return f'{self._url}/{self._course_public_repo}/blob/master'

    def get_url_for_repo(
            self,
            username: str,
    ) -> str:
        return f'{self._url}/{self._course_group}/{username}'


def map_gitlab_user_to_student(
        gitlab_response: gitlab.v4.objects.User,
) -> Student:
    return Student(
        id=gitlab_response.id,
        username=gitlab_response.username,
        name=gitlab_response.name,
        repo=gitlab_response.web_url,
    )
