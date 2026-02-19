from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalConfig:
    rms: str

    # gitlab
    gitlab_url: str
    gitlab_admin_token: str
    gitlab_verify_ssl: bool

    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str

    # sourcecraft
    sourcecraft_url: str
    sourcecraft_api_url: str
    sourcecraft_admin_token: str
    sourcecraft_org_slug: str

    # yandex_id
    yandex_id_client_id: str
    yandex_id_client_secret: str

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls(
            rms=os.environ.get("RMS", "GitLab").lower(),
            # gitlab
            gitlab_url=os.environ.get("GITLAB_URL", "https://gitlab.manytask2.org"),
            gitlab_admin_token=os.environ.get("GITLAB_ADMIN_TOKEN", ""),
            gitlab_verify_ssl=os.environ.get("GITLAB_VERIFY_SSL", "true").lower() in ("true", "1", "yes"),
            # gitlab oauth2
            gitlab_client_id=os.environ.get("GITLAB_CLIENT_ID", ""),
            gitlab_client_secret=os.environ.get("GITLAB_CLIENT_SECRET", ""),
            # sourcecraft
            sourcecraft_url=os.environ.get("SOURCRAFT_URL", "https://sourcecraft.dev"),
            sourcecraft_api_url=os.environ.get("SOURCRAFT_API_URL", "https://api.sourcecraft.tech"),
            sourcecraft_admin_token=os.environ.get("SOURCECRAFT_ADMIN_TOKEN", ""),
            sourcecraft_org_slug=os.environ.get("SOURCRAFT_ORG_SLUG", ""),
            # yandex_id
            yandex_id_client_id=os.environ.get("YANDEX_ID_CLIENT_ID", ""),
            yandex_id_client_secret=os.environ.get("YANDEX_ID_CLIENT_SECRET", ""),
        )


@dataclass
class DebugLocalConfig(LocalConfig):
    rms: str = "gitlab"
    # gitlab
    gitlab_url: str = "https://gitlab.manytask2.org"
    gitlab_admin_token: str = ""
    gitlab_verify_ssl: bool = True

    # gitlab oauth2
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""

    # sourcecraft
    sourcecraft_url: str = "https://sourcecraft.dev"
    sourcecraft_api_url: str = "https://api.sourcecraft.tech"
    sourcecraft_admin_token: str = ""
    sourcecraft_org_slug: str = ""

    # yandex_id
    yandex_id_client_id: str = ""
    yandex_id_client_secret: str = ""

    show_allscores: bool = True

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls()


@dataclass
class TestConfig(DebugLocalConfig):
    show_allscores: bool = True
