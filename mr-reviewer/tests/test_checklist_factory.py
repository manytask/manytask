"""Unit tests for the checklist step factory."""

from __future__ import annotations

import pytest

from app.checklist.builtins import (
    FolderStructureStep,
    ForbiddenFilesStep,
    PipelinePassedStep,
)
from app.checklist.factory import build_check_step
from app.models import (
    FolderStructureStep as FolderStructureConfig,
)
from app.models import (
    ForbiddenFilesStep as ForbiddenFilesConfig,
)
from app.models import (
    PipelinePassedStep as PipelinePassedConfig,
)
from app.models import (
    RunStep as RunStepConfig,
)
from tests._fakes import FakeHostingAdapter


class TestBuildCheckStep:
    def test_builds_pipeline_passed(self, fake_hosting_adapter: "FakeHostingAdapter") -> None:
        step = build_check_step(
            PipelinePassedConfig(),
            hosting=fake_hosting_adapter,
            sandbox=None,
        )
        assert isinstance(step, PipelinePassedStep)

    def test_builds_forbidden_files(self, fake_hosting_adapter: "FakeHostingAdapter") -> None:
        step = build_check_step(
            ForbiddenFilesConfig(extensions=[".pyc"]),
            hosting=fake_hosting_adapter,
            sandbox=None,
        )
        assert isinstance(step, ForbiddenFilesStep)

    def test_builds_folder_structure(self, fake_hosting_adapter: "FakeHostingAdapter") -> None:
        step = build_check_step(
            FolderStructureConfig(required_path="tasks/foo"),
            hosting=fake_hosting_adapter,
            sandbox=None,
        )
        assert isinstance(step, FolderStructureStep)

    def test_run_without_sandbox_raises(self, fake_hosting_adapter: "FakeHostingAdapter") -> None:
        with pytest.raises(ValueError, match="run: step requires a RunSandbox"):
            build_check_step(
                RunStepConfig(command="echo hi"),
                hosting=fake_hosting_adapter,
                sandbox=None,
            )
