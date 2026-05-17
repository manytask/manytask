"""Unit tests for hosting domain dataclasses."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.hosting.models import Comment, FileChange, MergeRequest, PipelineStatus


class TestMergeRequest:
    def test_required_fields_only(self) -> None:
        mr = MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="abc1234",
            web_url="https://gitlab.example.com/group/proj/-/merge_requests/7",
            source_branch="task-1",
            target_branch="main",
            author_username="ivanov",
            labels=("review-needed",),
            title="task-1: solution",
        )
        assert mr.project_id == 42
        assert mr.labels == ("review-needed",)

    def test_is_frozen(self) -> None:
        mr = MergeRequest(
            project_id=1,
            mr_iid=1,
            sha="x",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=(),
            title="t",
        )
        with pytest.raises(FrozenInstanceError):
            mr.project_id = 2  # type: ignore[misc]

    def test_labels_are_hashable_tuple(self) -> None:
        mr = MergeRequest(
            project_id=1,
            mr_iid=1,
            sha="x",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=("a", "b"),
            title="t",
        )
        assert isinstance(mr.labels, tuple)
        assert hash(mr) == hash(mr)


class TestComment:
    def test_required_fields(self) -> None:
        c = Comment(
            id=12345,
            author_username="petrov",
            body="hello",
            created_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        )
        assert c.id == 12345
        assert c.author_username == "petrov"

    def test_is_frozen(self) -> None:
        c = Comment(
            id=1,
            author_username="u",
            body="b",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(FrozenInstanceError):
            c.body = "y"  # type: ignore[misc]


class TestFileChange:
    def test_default_flags(self) -> None:
        change = FileChange(
            old_path="a/b.py",
            new_path="a/b.py",
            new_file=False,
            renamed_file=False,
            deleted_file=False,
            diff="@@ ...",
        )
        assert change.diff.startswith("@@")
        assert change.new_path == change.old_path

    def test_rename(self) -> None:
        change = FileChange(
            old_path="a/old.py",
            new_path="a/new.py",
            new_file=False,
            renamed_file=True,
            deleted_file=False,
            diff="",
        )
        assert change.renamed_file is True


class TestPipelineStatus:
    def test_known_state(self) -> None:
        ps = PipelineStatus(
            id=99,
            state="success",
            web_url="https://gitlab.example.com/group/proj/-/pipelines/99",
            sha="abc",
        )
        assert ps.state == "success"

    def test_no_pipeline_state(self) -> None:
        ps = PipelineStatus(id=None, state="none", web_url=None, sha=None)
        assert ps.id is None
        assert ps.state == "none"
