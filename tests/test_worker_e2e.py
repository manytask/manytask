"""End-to-end: one poll cycle over real adapters with mocked HTTP."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx
import responses
import respx
from fakeredis.aioredis import FakeRedis

from app.checklist import ChecklistPublisher, ChecklistRunner, SummaryRenderer
from app.config import Settings
from app.hosting.gitlab_adapter import GitLabAdapter
from app.manytask import ManytaskClient
from app.models import CourseConfig
from app.storage import CourseStore, ProcessedCommentStore
from app.worker.loop import WorkerLoop
from app.worker.metrics import WorkerMetrics
from app.worker.score import ScoreProcessor

GITLAB = "https://gitlab.test"
MANYTASK = "http://manytask.test"
BOT = "manytask-mr-reviewer-bot"
PROJECT_ID = 42
IID = 7


def _config() -> CourseConfig:
    return CourseConfig.model_validate(
        {
            "gitlab_group": "course/students",
            "score_comment_pattern": "Score: {score}",
            "tasks": [{"name": "task-1", "checklist": [{"type": "pipeline_passed"}]}],
        }
    )


def _mr_summary_json() -> dict[str, object]:
    return {
        "id": 1000 + IID,
        "iid": IID,
        "project_id": PROJECT_ID,
        "title": "task-1: solution",
        "sha": "HEAD",
        "web_url": f"{GITLAB}/course/students/proj/-/merge_requests/{IID}",
        "source_branch": "task-1",
        "target_branch": "main",
        "labels": ["task-1"],
        "author": {"username": "student"},
        "state": "opened",
        "references": {"full": "course/students/proj!7"},
    }


def _mr_full_json() -> dict[str, object]:
    return {**_mr_summary_json(), "description": ""}


def _notes_json() -> list[dict[str, object]]:
    return [
        {
            "id": 10,
            "body": "Score: 350",
            "author": {"username": "teacher"},
            "created_at": "2026-05-01T10:00:00.000Z",
            "system": False,
        }
    ]


def _register_gitlab_mocks(gitlab_mock: responses.RequestsMock) -> None:
    gitlab_mock.add(
        responses.GET,
        f"{GITLAB}/api/v4/groups/course%2Fstudents/merge_requests",
        json=[_mr_summary_json()],
        status=200,
        match=[
            responses.matchers.query_param_matcher(
                {"state": "opened", "labels": "task-1", "per_page": "100"},
                strict_match=False,
            )
        ],
    )
    gitlab_mock.add(
        responses.GET,
        f"{GITLAB}/api/v4/projects/{PROJECT_ID}/merge_requests/{IID}/pipelines",
        json=[{"id": 9001, "status": "success", "sha": "HEAD", "web_url": "x"}],
        status=200,
    )
    notes_url = f"{GITLAB}/api/v4/projects/{PROJECT_ID}/merge_requests/{IID}/notes"
    for _ in range(3):
        gitlab_mock.add(responses.GET, notes_url, json=_notes_json(), status=200)
    gitlab_mock.add(
        responses.POST,
        notes_url,
        json={
            "id": 555,
            "body": "<!-- mr-reviewer:checklist:task-1 -->\n",
            "author": {"username": BOT},
            "created_at": "2026-05-01T10:00:00.000Z",
            "system": False,
        },
        status=201,
    )
    mr_url = f"{GITLAB}/api/v4/projects/{PROJECT_ID}/merge_requests/{IID}"
    for labels in (["task-1", "checklist"], ["task-1", "checklist"]):
        gitlab_mock.add(
            responses.PUT,
            mr_url,
            json={**_mr_full_json(), "labels": labels},
            status=200,
        )


async def test_full_cycle_reviews_and_reports_override() -> None:
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="e2e-gitlab")
    hosting = GitLabAdapter(token="t", base_url=GITLAB, executor=executor, batch_size=4)

    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    await course_store.upsert_course("python-101", _config(), course_token="course-tok")

    settings = Settings(poll_interval_sec=900.0, per_mr_timeout_sec=120.0)

    with responses.RequestsMock(assert_all_requests_are_fired=False) as gitlab_mock:
        _register_gitlab_mocks(gitlab_mock)

        with respx.mock(base_url=MANYTASK) as mock:
            mock.get("/api/python-101/is_admin").mock(
                return_value=httpx.Response(200, json={"rms_username": "teacher", "is_admin": True})
            )
            report_route = mock.post("/api/python-101/report").mock(
                return_value=httpx.Response(
                    200, json={"user_id": 1, "username": "student", "task": "task-1", "score": 350}
                )
            )

            manytask = ManytaskClient(base_url=MANYTASK, timeout_sec=2.0)
            try:
                loop = WorkerLoop(
                    course_store=course_store,
                    hosting=hosting,
                    runner=ChecklistRunner(hosting=hosting, sandbox=None),
                    publisher=ChecklistPublisher(
                        hosting=hosting,
                        renderer=SummaryRenderer(),
                        bot_username=BOT,
                        label_processed="checklist",
                        label_fail="fix it",
                    ),
                    score_processor=ScoreProcessor(
                        hosting=hosting,
                        manytask=manytask,
                        processed_store=ProcessedCommentStore(redis),
                        bot_username=BOT,
                    ),
                    settings=settings,
                    metrics=WorkerMetrics(),
                )

                await loop.run_cycle()
            finally:
                await manytask.aclose()
                executor.shutdown(wait=True, cancel_futures=True)

            assert report_route.called
            body = report_route.calls.last.request.content.decode()
            assert "score=350" in body
            assert "check_deadline=False" in body
            assert "allow_reduction=True" in body

            post_calls = [c for c in gitlab_mock.calls if c.request.method == "POST"]
            assert len(post_calls) == 1
            assert "mr-reviewer:checklist:task-1" in post_calls[0].request.body.decode()

            put_calls = [c for c in gitlab_mock.calls if c.request.method == "PUT"]
            assert len(put_calls) == 2
            put_bodies = [c.request.body.decode() for c in put_calls]
            assert any("checklist" in b for b in put_bodies)
            assert any("fix it" in b for b in put_bodies)
