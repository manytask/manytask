"""Integration tests for /courses HTTP API."""

from __future__ import annotations

import httpx
import respx
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient

from app.storage import CourseStore

VALID_MANYTASK_YAML = """
version: 1
ui:
  task_url_template: "https://gitlab.example.com/$GROUP_NAME/$USER_NAME/$TASK_NAME"

deadlines:
  timezone: Europe/Berlin
  schedule:
    - group: g0
      start: 2030-01-01 18:00
      end: 2030-05-01 23:59
      tasks:
        - task: t0
          score: 10

mr_review:
  schema_version: 1
  tasks:
    - name: task-1
      checklist:
        - type: pipeline_passed
        - type: forbidden_files
          extensions: [".env"]
"""


def _ping_url(course: str) -> str:
    return f"http://manytask.test/api/{course}/ping"


class TestPostCourse:
    @respx.mock  # type: ignore[misc]
    async def test_valid_token_creates_course(
        self,
        client_with_overrides: AsyncClient,
        fake_redis: FakeRedis,
    ) -> None:
        respx.get(_ping_url("python-101")).mock(
            return_value=httpx.Response(200, json={"course": "python-101", "ok": True})
        )

        response = await client_with_overrides.post(
            "/courses/python-101",
            content=VALID_MANYTASK_YAML.encode(),
            headers={
                "Authorization": "Bearer course-tok-A",
                "Content-Type": "application/x-yaml",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "python-101"
        assert body["schema_version"] == 1
        assert body["tasks_count"] == 1

        store = CourseStore(fake_redis)
        loaded = await store.get_course("python-101")
        assert loaded is not None
        _, cfg, token = loaded
        assert token == "course-tok-A"
        assert cfg.tasks[0].name == "task-1"

    @respx.mock  # type: ignore[misc]
    async def test_invalid_token_returns_403(self, client_with_overrides: AsyncClient) -> None:
        respx.get(_ping_url("python-101")).mock(return_value=httpx.Response(403))

        response = await client_with_overrides.post(
            "/courses/python-101",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer wrong", "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 403

    @respx.mock  # type: ignore[misc]
    async def test_unknown_course_returns_404(self, client_with_overrides: AsyncClient) -> None:
        respx.get(_ping_url("ghost")).mock(return_value=httpx.Response(404))

        response = await client_with_overrides.post(
            "/courses/ghost",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 404

    @respx.mock  # type: ignore[misc]
    async def test_manytask_unavailable_returns_502(self, client_with_overrides: AsyncClient) -> None:
        respx.get(_ping_url("python-101")).mock(return_value=httpx.Response(500))

        response = await client_with_overrides.post(
            "/courses/python-101",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 502

    async def test_missing_authorization_returns_403(self, client_with_overrides: AsyncClient) -> None:
        response = await client_with_overrides.post(
            "/courses/python-101",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 403

    @respx.mock  # type: ignore[misc]
    async def test_invalid_yaml_returns_422(self, client_with_overrides: AsyncClient) -> None:
        respx.get(_ping_url("python-101")).mock(
            return_value=httpx.Response(200, json={"course": "python-101", "ok": True})
        )

        response = await client_with_overrides.post(
            "/courses/python-101",
            content=b"mr_review: [\n  - oops\n",
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 422
        body = response.json()
        assert "yaml" in str(body).lower() or "mr_review" in str(body).lower()

    @respx.mock  # type: ignore[misc]
    async def test_yaml_without_mr_review_returns_422(
        self,
        client_with_overrides: AsyncClient,
    ) -> None:
        respx.get(_ping_url("python-101")).mock(
            return_value=httpx.Response(200, json={"course": "python-101", "ok": True})
        )

        response = await client_with_overrides.post(
            "/courses/python-101",
            content=b"version: 1\nui: {}\n",
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 422
        assert "mr_review" in str(response.json()).lower()

    @respx.mock  # type: ignore[misc]
    async def test_invalid_mr_review_step_returns_422(
        self,
        client_with_overrides: AsyncClient,
    ) -> None:
        respx.get(_ping_url("python-101")).mock(
            return_value=httpx.Response(200, json={"course": "python-101", "ok": True})
        )

        bad_yaml = b"""
mr_review:
  schema_version: 1
  tasks:
    - name: task-1
      checklist:
        - type: forbidden_files
"""

        response = await client_with_overrides.post(
            "/courses/python-101",
            content=bad_yaml,
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 422
        assert "extensions" in str(response.json())

    @respx.mock  # type: ignore[misc]
    async def test_cross_course_token_rejected(
        self,
        client_with_overrides: AsyncClient,
    ) -> None:
        respx.get(_ping_url("course-a")).mock(return_value=httpx.Response(200, json={"course": "course-a", "ok": True}))
        respx.get(_ping_url("course-b")).mock(return_value=httpx.Response(403))

        ok = await client_with_overrides.post(
            "/courses/course-a",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer tok-A", "Content-Type": "application/x-yaml"},
        )
        assert ok.status_code == 201

        rejected = await client_with_overrides.post(
            "/courses/course-b",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer tok-A", "Content-Type": "application/x-yaml"},
        )
        assert rejected.status_code == 403

    @respx.mock  # type: ignore[misc]
    async def test_second_call_uses_cache_and_skips_ping(
        self,
        client_with_overrides: AsyncClient,
    ) -> None:
        route = respx.get(_ping_url("python-101")).mock(
            return_value=httpx.Response(200, json={"course": "python-101", "ok": True})
        )

        first = await client_with_overrides.post(
            "/courses/python-101",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )
        second = await client_with_overrides.post(
            "/courses/python-101",
            content=VALID_MANYTASK_YAML.encode(),
            headers={"Authorization": "Bearer tok", "Content-Type": "application/x-yaml"},
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert route.call_count == 1, "second POST must hit the positive cache, not manytask"
