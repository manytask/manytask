"""Unit tests for the pipeline_passed built-in step."""

from __future__ import annotations

import pytest

from app.checklist.builtins.pipeline_passed import PipelinePassedStep
from app.checklist.step import CheckContext
from app.hosting import MergeRequest, PipelineStatus
from tests._fakes import FakeHostingAdapter


class TestPipelinePassed:
    async def test_passes_when_status_success(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.pipeline_status = PipelineStatus(
            id=1, state="success", web_url="https://gitlab.test/pipelines/1", sha="x"
        )
        step = PipelinePassedStep(hosting=fake_hosting_adapter)

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True
        assert result.name == "pipeline passed"

    @pytest.mark.parametrize(
        "state",
        ["failed", "running", "canceled", "pending", "skipped", "manual", "none"],
    )
    async def test_fails_on_non_success(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
        state: str,
    ) -> None:
        fake_hosting_adapter.pipeline_status = PipelineStatus(
            id=None,
            state=state,  # type: ignore[arg-type]
            web_url=None,
            sha=None,
        )
        step = PipelinePassedStep(hosting=fake_hosting_adapter)

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert state in result.message

    async def test_message_includes_pipeline_url_on_failure(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.pipeline_status = PipelineStatus(
            id=99, state="failed", web_url="https://gitlab.test/pipelines/99", sha="x"
        )
        step = PipelinePassedStep(hosting=fake_hosting_adapter)

        result = await step.run(sample_mr, sample_ctx)

        assert "https://gitlab.test/pipelines/99" in result.message
