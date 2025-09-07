from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalConfig:
    # basic
    auth_backend: str
    rms_backend: str

    # gitlab
    gitlab_url: str
    gitlab_admin_token: str

    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str

    # yandex oauth2
    yandex_client_id: str
    yandex_client_secret: str

    # sourcecraft
    sourcecraft_base_url: str
    sourcecraft_api_url: str
    sourcecraft_admin_token: str
    sourcecraft_org_slug: str

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls(
            # basic
            auth_backend=os.environ.get("AUTH_BACKEND", "gitlab"),
            rms_backend=os.environ.get("RMS_BACKEND", "gitlab"),
            # gitlab
            gitlab_url=os.environ.get("GITLAB_URL", "https://gitlab.manytask.org"),
            gitlab_admin_token=os.environ["GITLAB_ADMIN_TOKEN"],
            # gitlab oauth2
            gitlab_client_id=os.environ["GITLAB_CLIENT_ID"],
            gitlab_client_secret=os.environ["GITLAB_CLIENT_SECRET"],
            # yandex oauth2
            yandex_client_id=os.environ["YANDEX_CLIENT_ID"],
            yandex_client_secret=os.environ["YANDEX_CLIENT_SECRET"],
            # sourcecraft
            sourcecraft_base_url=os.environ.get("SOURCECRAFT_URL", "https://sourcecraft.dev"),
            sourcecraft_api_url=os.environ.get("SOURCECRAFT_API_URL", "https://api.sourcecraft.tech"),
            sourcecraft_org_slug=os.environ.get("SOURCECRAFT_ORG_SLUG", "manytask"),
            sourcecraft_admin_token=os.environ["SOURCECRAFT_ADMIN_TOKEN"],
        )


@dataclass
class DebugLocalConfig(LocalConfig):
    # basic
    auth_backend: str = "sourcecraft"
    rms_backend: str = "sourcecraft"

    # gitlab
    gitlab_url: str = "https://gitlab.manytask.org"
    gitlab_admin_token: str = ""

    # gitlab oauth2
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""

    # yandex oauth2 (debug values)
    yandex_client_id: str = "debug_yandex_client_id"
    yandex_client_secret: str = "debug_yandex_client_secret"

    # sourcecraft
    sourcecraft_base_url: str = "https://sourcecraft.dev"
    sourcecraft_api_url: str = "https://api.sourcecraft.tech"
    sourcecraft_org_slug: str = "manytask"
    sourcecraft_admin_token: str = ""

    show_allscores: bool = True

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls()


@dataclass
class TestConfig(DebugLocalConfig):
    show_allscores: bool = True
