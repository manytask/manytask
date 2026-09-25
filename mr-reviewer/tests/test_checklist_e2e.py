"""End-to-end test of ChecklistRunner + ChecklistPublisher over real GitLabAdapter."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import responses

from app.checklist import ChecklistPublisher, ChecklistRunner
from app.checklist.render import SummaryRenderer
from app.checklist.sandbox import RunSandbox
from app.checklist.step import CheckContext
from app.hosting.gitlab_adapter import GitLabAdapter
from app.hosting.models import MergeRequest
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
from app.models import (
    TaskConfig,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required for e2e test")


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True)


@pytest.fixture
def bare_remote_for_e2e(tmp_path: Path) -> Path:
    upstream = tmp_path / "upstream.git"
    _run(["git", "init", "--bare", "-b", "main", str(upstream)])

    work = tmp_path / "work"
    _run(["git", "init", "-b", "main", str(work)])
    _run(["git", "-C", str(work), "config", "user.email", "t@t"])
    _run(["git", "-C", str(work), "config", "user.name", "t"])
    (work / "tasks" / "task-1").mkdir(parents=True)
    (work / "tasks" / "task-1" / "main.py").write_text("print('hi')\n")
    _run(["git", "-C", str(work), "add", "."])
    _run(["git", "-C", str(work), "commit", "-m", "initial"])
    _run(["git", "-C", str(work), "checkout", "-b", "task-1"])
    _run(["git", "-C", str(work), "remote", "add", "origin", str(upstream)])
    _run(["git", "-C", str(work), "push", "origin", "main", "task-1"])
    return upstream


def _mr_json(*, iid: int = 7, project_id: int = 42) -> dict[str, Any]:
    return {
        "id": 1000 + iid,
        "iid": iid,
        "project_id": project_id,
        "title": "task-1: solution",
        "sha": "HEAD",
        "web_url": f"https://gitlab.test/group/proj/-/merge_requests/{iid}",
        "source_branch": "task-1",
        "target_branch": "main",
        "labels": ["review-needed"],
        "author": {"username": "student"},
        "state": "opened",
    }


class TestChecklistE2E:
    def test_full_round_trip_and_idempotent_update(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
        bare_remote_for_e2e: Path,
        bot_username: str,
    ) -> None:
        project_id, iid = 42, 7

        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/pipelines",
            json=[{"id": 9001, "status": "success", "sha": "HEAD", "web_url": "x"}],
            status=200,
        )
        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/changes",
            json={
                **_mr_json(iid=iid, project_id=project_id),
                "changes": [
                    {
                        "old_path": "tasks/task-1/main.py",
                        "new_path": "tasks/task-1/main.py",
                        "new_file": False,
                        "renamed_file": False,
                        "deleted_file": False,
                        "diff": "@@",
                    }
                ],
            },
            status=200,
        )
        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/changes",
            json={
                **_mr_json(iid=iid, project_id=project_id),
                "changes": [
                    {
                        "old_path": "tasks/task-1/main.py",
                        "new_path": "tasks/task-1/main.py",
                        "new_file": False,
                        "renamed_file": False,
                        "deleted_file": False,
                        "diff": "@@",
                    }
                ],
            },
            status=200,
        )
        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/notes",
            json=[],
            status=200,
        )
        mock_gitlab.add(
            responses.POST,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/notes",
            json={
                "id": 555,
                "body": "<!-- mr-reviewer:checklist:task-1 -->\n",
                "author": {"username": bot_username},
                "created_at": "2026-05-01T10:00:00.000Z",
                "system": False,
            },
            status=201,
        )
        mock_gitlab.add(
            responses.PUT,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}",
            json={**_mr_json(iid=iid, project_id=project_id), "labels": ["review-needed", "checklist"]},
            status=200,
        )

        mr = MergeRequest(
            project_id=project_id,
            mr_iid=iid,
            sha="HEAD",
            web_url=f"https://gitlab.test/group/proj/-/merge_requests/{iid}",
            source_branch="task-1",
            target_branch="main",
            author_username="student",
            labels=("review-needed",),
            title="task-1: solution",
            project_path_with_namespace=str(bare_remote_for_e2e),
        )

        sandbox = RunSandbox(
            hosting=gitlab_adapter,
            gitlab_base_url="file://",
            gitlab_token="ignored",
            manytask_base_url="http://manytask.test",
            timeout_sec=5.0,
            env_whitelist_extra={},
            clone_url_builder=lambda m: f"file://{bare_remote_for_e2e}",
        )
        runner = ChecklistRunner(hosting=gitlab_adapter, sandbox=sandbox)
        publisher = ChecklistPublisher(
            hosting=gitlab_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        task = TaskConfig(
            name="task-1",
            checklist=[
                PipelinePassedConfig(),
                ForbiddenFilesConfig(extensions=[".pyc"]),
                FolderStructureConfig(required_path="tasks/task-1"),
                RunStepConfig(command="echo hello"),
            ],
        )

        async def go() -> list[Any]:
            results = await runner.run(
                task,
                mr,
                CheckContext(course_name="python-101", course_token="t"),
            )
            await publisher.publish(mr=mr, task_name="task-1", results=results)
            return results

        results = asyncio.run(go())

        assert all(r.passed for r in results), [(r.name, r.message) for r in results if not r.passed]

        post_notes = [
            c
            for c in mock_gitlab.calls
            if c.request.method == "POST" and c.request.url.endswith(f"/merge_requests/{iid}/notes")
        ]
        assert len(post_notes) == 1, "first publish must POST a fresh comment"

    def test_second_run_updates_same_comment(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
        bare_remote_for_e2e: Path,
        bot_username: str,
    ) -> None:
        project_id, iid = 42, 7

        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/pipelines",
            json=[{"id": 9001, "status": "success", "sha": "HEAD", "web_url": "x"}],
            status=200,
        )
        for _ in range(2):
            mock_gitlab.add(
                responses.GET,
                f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/changes",
                json={
                    **_mr_json(iid=iid, project_id=project_id),
                    "changes": [
                        {
                            "old_path": "tasks/task-1/main.py",
                            "new_path": "tasks/task-1/main.py",
                            "new_file": False,
                            "renamed_file": False,
                            "deleted_file": False,
                            "diff": "",
                        }
                    ],
                },
                status=200,
            )
        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/notes",
            json=[
                {
                    "id": 555,
                    "body": "<!-- mr-reviewer:checklist:task-1 -->\nold",
                    "author": {"username": bot_username},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                }
            ],
            status=200,
        )
        mock_gitlab.add(
            responses.PUT,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/notes/555",
            json={
                "id": 555,
                "body": "<!-- mr-reviewer:checklist:task-1 -->\nnew",
                "author": {"username": bot_username},
                "created_at": "2026-05-01T10:00:00.000Z",
                "system": False,
            },
            status=200,
        )
        mock_gitlab.add(
            responses.PUT,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}",
            json={**_mr_json(iid=iid, project_id=project_id), "labels": ["checklist"]},
            status=200,
        )

        mr = MergeRequest(
            project_id=project_id,
            mr_iid=iid,
            sha="HEAD",
            web_url=f"https://gitlab.test/group/proj/-/merge_requests/{iid}",
            source_branch="task-1",
            target_branch="main",
            author_username="student",
            labels=(),
            title="t",
            project_path_with_namespace=str(bare_remote_for_e2e),
        )

        sandbox = RunSandbox(
            hosting=gitlab_adapter,
            gitlab_base_url="file://",
            gitlab_token="ignored",
            manytask_base_url="http://manytask.test",
            timeout_sec=5.0,
            env_whitelist_extra={},
            clone_url_builder=lambda m: f"file://{bare_remote_for_e2e}",
        )
        runner = ChecklistRunner(hosting=gitlab_adapter, sandbox=sandbox)
        publisher = ChecklistPublisher(
            hosting=gitlab_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        task = TaskConfig(
            name="task-1",
            checklist=[
                PipelinePassedConfig(),
                FolderStructureConfig(required_path="tasks/task-1"),
                RunStepConfig(command="echo hi"),
            ],
        )

        async def go() -> None:
            results = await runner.run(task, mr, CheckContext(course_name="c", course_token="t"))
            await publisher.publish(mr=mr, task_name="task-1", results=results)

        asyncio.run(go())

        post_notes = [
            c
            for c in mock_gitlab.calls
            if c.request.method == "POST" and c.request.url.endswith(f"/merge_requests/{iid}/notes")
        ]
        put_notes = [c for c in mock_gitlab.calls if c.request.method == "PUT" and "/notes/555" in c.request.url]
        assert post_notes == [], "must not POST a new comment when an anchored one exists"
        assert len(put_notes) == 1, "must UPDATE the existing comment exactly once"

    def test_forged_anchor_in_student_comment_is_ignored(
        self,
        gitlab_adapter: GitLabAdapter,
        mock_gitlab: responses.RequestsMock,
        bare_remote_for_e2e: Path,
        bot_username: str,
    ) -> None:
        project_id, iid = 42, 7

        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/pipelines",
            json=[{"id": 9001, "status": "success", "sha": "HEAD", "web_url": "x"}],
            status=200,
        )
        for _ in range(2):
            mock_gitlab.add(
                responses.GET,
                f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/changes",
                json={
                    **_mr_json(iid=iid, project_id=project_id),
                    "changes": [
                        {
                            "old_path": "tasks/task-1/main.py",
                            "new_path": "tasks/task-1/main.py",
                            "new_file": False,
                            "renamed_file": False,
                            "deleted_file": False,
                            "diff": "",
                        }
                    ],
                },
                status=200,
            )
        mock_gitlab.add(
            responses.GET,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/notes",
            json=[
                {
                    "id": 42,
                    "body": "<!-- mr-reviewer:checklist:task-1 -->\nFAKE — score 100",
                    "author": {"username": "evil-student"},
                    "created_at": "2026-05-01T10:00:00.000Z",
                    "system": False,
                }
            ],
            status=200,
        )
        mock_gitlab.add(
            responses.POST,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}/notes",
            json={
                "id": 777,
                "body": "<!-- mr-reviewer:checklist:task-1 -->\nreal",
                "author": {"username": bot_username},
                "created_at": "2026-05-01T11:00:00.000Z",
                "system": False,
            },
            status=201,
        )
        mock_gitlab.add(
            responses.PUT,
            f"https://gitlab.test/api/v4/projects/{project_id}/merge_requests/{iid}",
            json={**_mr_json(iid=iid, project_id=project_id), "labels": ["checklist"]},
            status=200,
        )

        mr = MergeRequest(
            project_id=project_id,
            mr_iid=iid,
            sha="HEAD",
            web_url=f"https://gitlab.test/group/proj/-/merge_requests/{iid}",
            source_branch="task-1",
            target_branch="main",
            author_username="student",
            labels=(),
            title="t",
            project_path_with_namespace=str(bare_remote_for_e2e),
        )

        sandbox = RunSandbox(
            hosting=gitlab_adapter,
            gitlab_base_url="file://",
            gitlab_token="ignored",
            manytask_base_url="http://manytask.test",
            timeout_sec=5.0,
            env_whitelist_extra={},
            clone_url_builder=lambda m: f"file://{bare_remote_for_e2e}",
        )
        runner = ChecklistRunner(hosting=gitlab_adapter, sandbox=sandbox)
        publisher = ChecklistPublisher(
            hosting=gitlab_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        task = TaskConfig(
            name="task-1",
            checklist=[
                PipelinePassedConfig(),
                FolderStructureConfig(required_path="tasks/task-1"),
                RunStepConfig(command="echo hi"),
            ],
        )

        async def go() -> None:
            results = await runner.run(task, mr, CheckContext(course_name="c", course_token="t"))
            await publisher.publish(mr=mr, task_name="task-1", results=results)

        asyncio.run(go())

        post_notes = [
            c
            for c in mock_gitlab.calls
            if c.request.method == "POST" and c.request.url.endswith(f"/merge_requests/{iid}/notes")
        ]
        put_to_forged = [c for c in mock_gitlab.calls if c.request.method == "PUT" and "/notes/42" in c.request.url]
        assert len(post_notes) == 1, "bot must POST its own comment"
        assert put_to_forged == [], "bot must never UPDATE a forged student comment"
