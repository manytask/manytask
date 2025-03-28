from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalConfig:
    # token
    manytask_app_token: str

    # utils
    cache_dir: str
    solutions_dir: str

    # gitlab
    gitlab_url: str
    gitlab_admin_token: str

    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls(
            # token
            manytask_app_token=os.environ["MANYTASK_APP_TOKEN"],
            # utils
            cache_dir=os.environ["CACHE_DIR"],
            solutions_dir=os.environ["SOLUTIONS_DIR"],
            # gitlab
            gitlab_url=os.environ.get("GITLAB_URL", "https://gitlab.manytask.org"),
            gitlab_admin_token=os.environ["GITLAB_ADMIN_TOKEN"],
            # gitlab oauth2
            gitlab_client_id=os.environ["GITLAB_CLIENT_ID"],
            gitlab_client_secret=os.environ["GITLAB_CLIENT_SECRET"],
        )


@dataclass
class DebugLocalConfig(LocalConfig):
    # token
    manytask_app_token: str = "token"

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

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls()


@dataclass
class TestConfig(DebugLocalConfig):
    pass
