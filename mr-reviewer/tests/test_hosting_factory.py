"""Tests for hosting adapter factory."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.hosting.factory import build_hosting_adapter
from app.hosting.gitlab_adapter import GitLabAdapter


class TestBuildHostingAdapter:
    def test_gitlab_returns_gitlab_adapter(
        self,
        gitlab_executor: ThreadPoolExecutor,
    ) -> None:
        adapter = build_hosting_adapter(
            "gitlab",
            gitlab_token="t",  # noqa: S106
            gitlab_base_url="https://gitlab.test",
            executor=gitlab_executor,
        )
        assert isinstance(adapter, GitLabAdapter)

    def test_unknown_hosting_type_raises(
        self,
        gitlab_executor: ThreadPoolExecutor,
    ) -> None:
        with pytest.raises(ValueError, match="unsupported hosting_type"):
            build_hosting_adapter(
                "github",
                gitlab_token="t",  # noqa: S106
                gitlab_base_url="https://gitlab.test",
                executor=gitlab_executor,
            )

    def test_sourcecraft_not_supported_yet(
        self,
        gitlab_executor: ThreadPoolExecutor,
    ) -> None:
        with pytest.raises(ValueError):
            build_hosting_adapter(
                "sourcecraft",
                gitlab_token="t",  # noqa: S106
                gitlab_base_url="https://gitlab.test",
                executor=gitlab_executor,
            )
