"""Build the right HostingClient for the configured provider."""

from app.config import Settings
from app.hosting.gitlab_adapter import GitLabHostingClient
from app.hosting.protocol import HostingClient


def build_hosting_client(settings: Settings) -> HostingClient:
    """TODO: dispatch on a provider field once multi-provider lands."""
    return GitLabHostingClient(token=settings.gitlab_token, base_url="https://gitlab.com")
