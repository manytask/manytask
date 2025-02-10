from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalConfig:
    # tokens
    registration_secret: str
    course_token: str

    # utils
    cache_dir: str
    solutions_dir: str

    # gitlab
    gitlab_url: str
    gitlab_admin_token: str
    # gitlab course repos
    gitlab_course_group: str
    gitlab_course_public_repo: str
    gitlab_course_students_group: str
    gitlab_default_branch: str
    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str
    # show link to all scores
    show_allscores: bool

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls(
            # tokens
            registration_secret=os.environ["REGISTRATION_SECRET"],
            course_token=os.environ["MANYTASK_COURSE_TOKEN"],
            # utils
            cache_dir=os.environ["CACHE_DIR"],
            solutions_dir=os.environ["SOLUTIONS_DIR"],
            # gitlab
            gitlab_url=os.environ.get("GITLAB_URL", "https://gitlab.manytask.org"),
            gitlab_admin_token=os.environ["GITLAB_ADMIN_TOKEN"],
            # gitlab course repos
            gitlab_course_group=os.environ["GITLAB_COURSE_GROUP"],
            gitlab_course_public_repo=os.environ["GITLAB_COURSE_PUBLIC_REPO"],
            gitlab_course_students_group=os.environ["GITLAB_COURSE_STUDENTS_GROUP"],
            gitlab_default_branch=os.environ.get("GITLAB_DEFAULT_BRANCH", "main"),
            # gitlab oauth2
            gitlab_client_id=os.environ["GITLAB_CLIENT_ID"],
            gitlab_client_secret=os.environ["GITLAB_CLIENT_SECRET"],
            # show link to all scores
            show_allscores=os.environ.get("SHOW_ALLSCORES", "True").lower() in ("true", "1", "yes"),
        )


@dataclass
class DebugLocalConfig(LocalConfig):
    # tokens
    registration_secret: str = "registration_secret"
    course_token: str = "token"

    # utils
    cache_dir: str = ".tmp/cache"
    solutions_dir: str = ".tmp/solutions"

    # gitlab
    gitlab_url: str = "https://gitlab.manytask.org"
    gitlab_admin_token: str = ""
    # gitlab course repos
    gitlab_course_group: str = ""
    gitlab_course_public_repo: str = ""
    gitlab_course_students_group: str = ""
    gitlab_default_branch: str = "main"
    # gitlab oauth2
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""

    show_allscores: bool = True

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls(
            show_allscores=os.environ.get("SHOW_ALLSCORES", "True").lower() in ("true", "1", "yes"),
        )


@dataclass
class TestConfig(DebugLocalConfig):
    show_allscores: bool = True
