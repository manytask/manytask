"""Integration tests for GitLabAdapter against responses-mocked GitLab API."""

from __future__ import annotations

import pytest
import responses

from app.hosting.gitlab_adapter import GitLabAdapter


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
