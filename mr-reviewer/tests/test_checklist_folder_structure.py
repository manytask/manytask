"""Unit tests for the folder_structure built-in step."""

from __future__ import annotations

from app.checklist.builtins.folder_structure import FolderStructureStep
from app.checklist.step import CheckContext
from app.hosting import FileChange, MergeRequest
from tests._fakes import FakeHostingAdapter


def _change(path: str, *, deleted: bool = False) -> FileChange:
    return FileChange(
        old_path=path,
        new_path=path,
        new_file=False,
        renamed_file=False,
        deleted_file=deleted,
        diff="",
    )


class TestFolderStructure:
    async def test_passes_when_all_changes_inside_prefix(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [
            _change("tasks/foo/main.py"),
            _change("tasks/foo/README.md"),
        ]
        step = FolderStructureStep(hosting=fake_hosting_adapter, required_path="tasks/foo")

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True

    async def test_fails_on_change_outside_prefix(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [
            _change("tasks/foo/main.py"),
            _change("docs/README.md"),
        ]
        step = FolderStructureStep(hosting=fake_hosting_adapter, required_path="tasks/foo")

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert "docs/README.md" in result.message

    async def test_normalizes_trailing_slash(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [_change("tasks/foo/main.py")]
        step = FolderStructureStep(hosting=fake_hosting_adapter, required_path="tasks/foo/")

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True

    async def test_prefix_must_be_full_segment(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        """`tasks/foo` must not match `tasks/foobar/`."""
        fake_hosting_adapter.changes = [_change("tasks/foobar/main.py")]
        step = FolderStructureStep(hosting=fake_hosting_adapter, required_path="tasks/foo")

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert "tasks/foobar/main.py" in result.message

    async def test_skips_deleted_files(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = [_change("docs/old.md", deleted=True)]
        step = FolderStructureStep(hosting=fake_hosting_adapter, required_path="tasks/foo")

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True

    async def test_empty_changes_passes(
        self,
        fake_hosting_adapter: FakeHostingAdapter,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        fake_hosting_adapter.changes = []
        step = FolderStructureStep(hosting=fake_hosting_adapter, required_path="tasks/foo")

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True
