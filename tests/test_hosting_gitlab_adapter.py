"""Integration tests for GitLabAdapter against responses-mocked GitLab API."""

from __future__ import annotations

import pytest
import responses

from app.hosting.gitlab_adapter import GitLabAdapter
from app.hosting.models import MergeRequest


def _mr_summary(project_id: int, iid: int, *, label: str = "review-needed") -> dict[str, object]:
    return {
        "id": 1000 + iid,
        "iid": iid,
        "project_id": project_id,
        "title": f"task-{iid}: solution",
        "sha": f"deadbeef{iid:04x}",
        "web_url": f"https://gitlab.test/group/proj-{project_id}/-/merge_requests/{iid}",
        "source_branch": f"task-{iid}",
        "target_branch": "main",
        "labels": [label],
        "author": {"username": f"user-{iid}"},
        "state": "opened",
    }


class TestListOpenMrs:
    def test_returns_mrs_with_label(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/groups/yandex%2Fpython-101/merge_requests",
            json=[_mr_summary(42, 1), _mr_summary(42, 2)],
            status=200,
            match=[
                responses.matchers.query_param_matcher(
                    {"state": "opened", "labels": "review-needed", "per_page": "100"},
                    strict_match=False,
                )
            ],
        )

        import asyncio

        mrs = asyncio.run(gitlab_adapter.list_open_mrs("yandex/python-101", "review-needed"))

        assert len(mrs) == 2
        assert {mr.mr_iid for mr in mrs} == {1, 2}
        assert mrs[0].project_id == 42
        assert mrs[0].labels == ("review-needed",)
        assert mrs[0].author_username.startswith("user-")

    def test_paginates_via_link_header(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        page1 = [_mr_summary(42, i) for i in range(1, 101)]
        page2 = [_mr_summary(42, i) for i in range(101, 121)]

        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/groups/yandex%2Fpython-101/merge_requests",
            json=page1,
            status=200,
            headers={
                "Link": '<https://gitlab.test/api/v4/groups/yandex%2Fpython-101/merge_requests?page=2&per_page=100>; rel="next"',
                "X-Next-Page": "2",
            },
            match=[responses.matchers.query_param_matcher({"page": "1"}, strict_match=False)],
        )
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/groups/yandex%2Fpython-101/merge_requests",
            json=page2,
            status=200,
            headers={"X-Next-Page": ""},
            match=[responses.matchers.query_param_matcher({"page": "2"}, strict_match=False)],
        )

        import asyncio

        mrs = asyncio.run(gitlab_adapter.list_open_mrs("yandex/python-101", "review-needed"))

        assert len(mrs) == 120

    def test_empty_group_returns_empty_list(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/groups/empty/merge_requests",
            json=[],
            status=200,
        )

        import asyncio

        mrs = asyncio.run(gitlab_adapter.list_open_mrs("empty", "review-needed"))

        assert mrs == []

    def test_group_404_raises(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/groups/missing/merge_requests",
            json={"message": "404 Group Not Found"},
            status=404,
        )

        import asyncio

        import gitlab.exceptions

        with pytest.raises(gitlab.exceptions.GitlabListError):
            asyncio.run(gitlab_adapter.list_open_mrs("missing", "review-needed"))


def _mr_full(project_id: int, iid: int) -> dict[str, object]:
    base = _mr_summary(project_id, iid)
    base["description"] = ""
    return base


def _mr_changes(project_id: int, iid: int) -> dict[str, object]:
    return {
        **_mr_full(project_id, iid),
        "changes": [
            {
                "old_path": "src/main.py",
                "new_path": "src/main.py",
                "new_file": False,
                "renamed_file": False,
                "deleted_file": False,
                "diff": "@@ -1 +1 @@\n-old\n+new\n",
            },
            {
                "old_path": "README.md",
                "new_path": "docs/README.md",
                "new_file": False,
                "renamed_file": True,
                "deleted_file": False,
                "diff": "",
            },
        ],
    }


class TestGetMr:
    def test_fetches_full_mr(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7",
            json=_mr_full(42, 7),
            status=200,
        )

        import asyncio

        mr = asyncio.run(gitlab_adapter.get_mr(42, 7))

        assert mr.project_id == 42
        assert mr.mr_iid == 7
        assert mr.title == "task-7: solution"
        assert mr.author_username == "user-7"

    def test_404_propagates_gitlab_error(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/999",
            json={"message": "404 Not found"},
            status=404,
        )

        import asyncio

        import gitlab.exceptions

        with pytest.raises(gitlab.exceptions.GitlabGetError):
            asyncio.run(gitlab_adapter.get_mr(42, 999))


class TestGetChanges:
    def _mr(self, project_id: int = 42, iid: int = 7) -> MergeRequest:
        return MergeRequest(
            project_id=project_id,
            mr_iid=iid,
            sha="x",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=(),
            title="t",
        )

    def test_returns_changes(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/changes",
            json=_mr_changes(42, 7),
            status=200,
        )

        import asyncio

        changes = asyncio.run(gitlab_adapter.get_changes(self._mr()))

        assert len(changes) == 2
        assert changes[0].old_path == "src/main.py"
        assert changes[1].renamed_file is True

    def test_empty_diff(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        empty = _mr_full(42, 7)
        empty["changes"] = []
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/changes",
            json=empty,
            status=200,
        )

        import asyncio

        changes = asyncio.run(gitlab_adapter.get_changes(self._mr()))

        assert changes == []


class TestGetPipelineStatus:
    def _mr(self) -> "MergeRequest":
        from app.hosting.models import MergeRequest

        return MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="deadbeef",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=(),
            title="t",
        )

    def test_success_pipeline(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/pipelines",
            json=[
                {
                    "id": 9001,
                    "status": "success",
                    "sha": "deadbeef",
                    "web_url": "https://gitlab.test/group/proj-42/-/pipelines/9001",
                }
            ],
            status=200,
        )

        import asyncio

        ps = asyncio.run(gitlab_adapter.get_pipeline_status(self._mr()))

        assert ps.id == 9001
        assert ps.state == "success"
        assert ps.sha == "deadbeef"

    def test_no_pipeline_returns_none_state(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/pipelines",
            json=[],
            status=200,
        )

        import asyncio

        ps = asyncio.run(gitlab_adapter.get_pipeline_status(self._mr()))

        assert ps.id is None
        assert ps.state == "none"
        assert ps.web_url is None

    def test_unknown_state_falls_back_to_none(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/pipelines",
            json=[
                {
                    "id": 1,
                    "status": "weird-future-state",
                    "sha": "x",
                    "web_url": "x",
                }
            ],
            status=200,
        )

        import asyncio

        ps = asyncio.run(gitlab_adapter.get_pipeline_status(self._mr()))

        assert ps.state == "none"
        assert ps.id == 1


class TestGetComments:
    def _mr(self) -> "MergeRequest":
        from app.hosting.models import MergeRequest

        return MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="x",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=(),
            title="t",
        )

    def test_returns_all_when_no_since_id(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes",
            json=[
                {
                    "id": 100,
                    "body": "first",
                    "author": {"username": "alice"},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                },
                {
                    "id": 101,
                    "body": "second",
                    "author": {"username": "bob"},
                    "created_at": "2026-05-01T11:00:00.000Z",
                    "system": False,
                },
            ],
            status=200,
        )

        import asyncio

        comments = asyncio.run(gitlab_adapter.get_comments(self._mr()))

        assert [c.id for c in comments] == [100, 101]
        assert comments[0].author_username == "alice"
        assert comments[0].created_at.year == 2026

    def test_since_id_filter(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes",
            json=[
                {
                    "id": 100,
                    "body": "old",
                    "author": {"username": "u"},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                },
                {
                    "id": 101,
                    "body": "new",
                    "author": {"username": "u"},
                    "created_at": "2026-05-01T11:00:00.000Z",
                    "system": False,
                },
                {
                    "id": 102,
                    "body": "newer",
                    "author": {"username": "u"},
                    "created_at": "2026-05-01T12:00:00.000Z",
                    "system": False,
                },
            ],
            status=200,
        )

        import asyncio

        comments = asyncio.run(gitlab_adapter.get_comments(self._mr(), since_id=100))

        assert [c.id for c in comments] == [101, 102]

    def test_skips_system_notes(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes",
            json=[
                {
                    "id": 100,
                    "body": "human",
                    "author": {"username": "alice"},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                },
                {
                    "id": 101,
                    "body": "marked as draft",
                    "author": {"username": "alice"},
                    "created_at": "2026-05-01T11:00:00.000Z",
                    "system": True,
                },
            ],
            status=200,
        )

        import asyncio

        comments = asyncio.run(gitlab_adapter.get_comments(self._mr()))

        assert [c.id for c in comments] == [100]


class TestPostOrUpdateComment:
    def _mr(self) -> "MergeRequest":
        from app.hosting.models import MergeRequest

        return MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="x",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=(),
            title="t",
        )

    def test_creates_new_comment_when_no_anchor_match(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes",
            json=[
                {
                    "id": 1,
                    "body": "unrelated",
                    "author": {"username": "alice"},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                },
            ],
            status=200,
        )
        mock_gitlab.add(
            responses.POST,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes",
            json={
                "id": 999,
                "body": "<!-- mr-reviewer:score-task-1 -->\nscore: 100",
                "author": {"username": "bot"},
                "created_at": "2026-05-01T12:00:00.000Z",
                "system": False,
            },
            status=201,
        )

        import asyncio

        result = asyncio.run(gitlab_adapter.post_or_update_comment(self._mr(), "score-task-1", "score: 100"))

        assert result.id == 999
        assert "<!-- mr-reviewer:score-task-1 -->" in result.body

    def test_updates_existing_comment_with_matching_anchor(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.GET,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes",
            json=[
                {
                    "id": 1,
                    "body": "<!-- mr-reviewer:score-task-1 -->\nold body",
                    "author": {"username": "bot"},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                },
                {
                    "id": 2,
                    "body": "human reply",
                    "author": {"username": "alice"},
                    "created_at": "2026-05-01T11:00:00.000Z",
                    "system": False,
                },
            ],
            status=200,
        )
        mock_gitlab.add(
            responses.PUT,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7/notes/1",
            json={
                "id": 1,
                "body": "<!-- mr-reviewer:score-task-1 -->\nnew body",
                "author": {"username": "bot"},
                "created_at": "2026-05-01T10:00:00.000Z",
                "system": False,
            },
            status=200,
        )

        import asyncio

        result = asyncio.run(gitlab_adapter.post_or_update_comment(self._mr(), "score-task-1", "new body"))

        assert result.id == 1
        assert "new body" in result.body

        post_calls = [c for c in mock_gitlab.calls if c.request.method == "POST"]
        assert post_calls == [], "must not POST a new comment when an anchored one exists"


class TestLabels:
    def _mr(self, labels: tuple[str, ...] = ()) -> "MergeRequest":
        from app.hosting.models import MergeRequest

        return MergeRequest(
            project_id=42,
            mr_iid=7,
            sha="x",
            web_url="x",
            source_branch="s",
            target_branch="t",
            author_username="u",
            labels=labels,
            title="t",
        )

    def test_add_labels_uses_add_labels_query_param(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.PUT,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7",
            json={**_mr_full(42, 7), "labels": ["review-needed", "needs-review"]},
            status=200,
        )

        import asyncio

        result = asyncio.run(gitlab_adapter.add_labels(self._mr(labels=("review-needed",)), ["needs-review"]))

        assert "needs-review" in result.labels
        last = mock_gitlab.calls[-1]
        assert last.request.method == "PUT"
        assert (
            "needs-review" in last.request.body.decode()
            if isinstance(last.request.body, (bytes, bytearray))
            else "needs-review" in str(last.request.body)
        )

    def test_remove_labels_uses_remove_labels_query_param(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
    ) -> None:
        mock_gitlab.add(
            responses.PUT,
            "https://gitlab.test/api/v4/projects/42/merge_requests/7",
            json={**_mr_full(42, 7), "labels": []},
            status=200,
        )

        import asyncio

        result = asyncio.run(gitlab_adapter.remove_labels(self._mr(labels=("review-needed",)), ["review-needed"]))

        assert "review-needed" not in result.labels


class TestGetAuthorUsername:
    def test_returns_author(self, gitlab_adapter: GitLabAdapter) -> None:
        from datetime import datetime, timezone

        from app.hosting.models import Comment

        c = Comment(
            id=1,
            author_username="ivanov",
            body="x",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        assert gitlab_adapter.get_author_username(c) == "ivanov"
