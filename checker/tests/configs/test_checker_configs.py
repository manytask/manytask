from __future__ import annotations

import pytest

from checker.configs import CheckerExportConfig


class TestCheckerExportConfig:
    def test_push_options_default(self) -> None:
        """By default `push_options` is `["ci.skip"]` to preserve backward-compatible
        GitLab behavior (skip pipelines on the auto-export commit)."""
        config = CheckerExportConfig(destination="https://example.com")
        assert config.push_options == ["ci.skip"]

    def test_push_options_default_is_not_shared(self) -> None:
        """Distinct instances must not share the same default list object."""
        a = CheckerExportConfig(destination="https://example.com")
        b = CheckerExportConfig(destination="https://example.com")
        a.push_options.append("mutated")
        assert b.push_options == ["ci.skip"]

    @pytest.mark.parametrize(
        "push_options",
        [
            [],
            ["ci.skip"],
            ["ci.skip", "merge_request.create"],
            ["custom-option"],
        ],
    )
    def test_push_options_override(self, push_options: list[str]) -> None:
        """`push_options` can be set to any list of strings, including an empty list
        (used for git servers that reject push options, e.g. SourceCraft)."""
        config = CheckerExportConfig(
            destination="https://example.com", push_options=push_options
        )
        assert config.push_options == push_options
