from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalConfig:
    # gitlab
    gitlab_url: str
    gitlab_admin_token: str
    gitlab_verify_ssl: bool

    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls(
            # gitlab
            gitlab_url=os.environ.get("GITLAB_URL", "https://gitlab.manytask2.org"),
            gitlab_admin_token=os.environ["GITLAB_ADMIN_TOKEN"],
            gitlab_verify_ssl=os.environ.get("GITLAB_VERIFY_SSL", "true").lower() == "true",
            # gitlab oauth2
            gitlab_client_id=os.environ["GITLAB_CLIENT_ID"],
            gitlab_client_secret=os.environ["GITLAB_CLIENT_SECRET"],
        )


@dataclass
class DebugLocalConfig(LocalConfig):
    # gitlab
    gitlab_url: str = "https://gitlab.manytask2.org"
    gitlab_admin_token: str = ""
    gitlab_verify_ssl: bool = True

    # gitlab oauth2
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""

    show_allscores: bool = True

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls()


@dataclass
class TestConfig(DebugLocalConfig):
    show_allscores: bool = True
