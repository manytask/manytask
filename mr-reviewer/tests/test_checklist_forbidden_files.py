"""Unit tests for the forbidden_files built-in step."""

from __future__ import annotations

from app.checklist.builtins.forbidden_files import ForbiddenFilesStep
from app.checklist.step import CheckContext
from app.hosting import FileChange, MergeRequest
from tests._fakes import FakeHostingAdapter


def _change(path: str, *, deleted: bool = False, new: bool = False) -> FileChange:
    return FileChange(
        old_path=path,
        new_path=path,
        new_file=new,
        renamed_file=False,
        deleted_file=deleted,
        diff="",
    )


class TestForbiddenFiles:
    async def test_passes_when_no_forbidden_extensions(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [_change("src/main.py"), _change("README.md")]
        step = ForbiddenFilesStep(hosting=fake_hosting_adapter, extensions=[".pyc", ".so"])

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True

    async def test_fails_on_forbidden_extension(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [
            _change("src/main.py"),
            _change("build/lib.so"),
        ]
        step = ForbiddenFilesStep(hosting=fake_hosting_adapter, extensions=[".so"])

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert "build/lib.so" in result.message

    async def test_normalizes_extension_without_dot(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [_change("artifact.pyc")]
        step = ForbiddenFilesStep(hosting=fake_hosting_adapter, extensions=["pyc"])

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert "artifact.pyc" in result.message

    async def test_skips_deleted_files(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [_change("legacy.so", deleted=True)]
        step = ForbiddenFilesStep(hosting=fake_hosting_adapter, extensions=[".so"])

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True

    async def test_reports_multiple_violations(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [
            _change("a.pyc"),
            _change("b.pyc"),
            _change("c.so"),
        ]
        step = ForbiddenFilesStep(hosting=fake_hosting_adapter, extensions=[".pyc", ".so"])

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        for p in ("a.pyc", "b.pyc", "c.so"):
            assert p in result.message
