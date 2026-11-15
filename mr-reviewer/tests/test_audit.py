"""Regression checks for write attempts, rejected requests and redaction."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.manytask import ManytaskClient, TokenAuthCache
from app.models import CURRENT_SCHEMA_VERSION, CourseConfig
from app.observability.audit import install_request_audit, set_audit_actor
from app.storage import CourseStore, ProcessedCommentStore


def entries(caplog: pytest.LogCaptureFixture, event: str) -> list[dict[str, Any]]:
    result = []
    for record in caplog.records:
        if record.name == "app.observability.audit":
            data = json.loads(record.getMessage())
            if data["event"] == event:
                result.append(data)
    return result


def config() -> CourseConfig:
    return CourseConfig.model_validate(
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "gitlab_group": "course/students",
            "tasks": [{"name": "task", "checklist": [{"type": "pipeline_passed"}]}],
        }
    )


async def test_all_redis_writers_log_attempt_and_completion(
    fake_redis: FakeRedis, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    store = CourseStore(fake_redis)
    await store.upsert_course("demo", config(), "private-token")
    await store.delete_course("demo")
    await ProcessedCommentStore(fake_redis).mark_processed("demo", "12", "34")
    await TokenAuthCache(fake_redis, ttl_sec=30).remember_valid("demo", "private-token")
    records = entries(caplog, "storage.write")
    assert {record["operation"] for record in records} == {
        "upsert_course",
        "delete_course",
        "mark_processed",
        "remember_valid",
    }
    for operation_id in {record["operation_id"] for record in records}:
        assert [record["outcome"] for record in records if record["operation_id"] == operation_id] == [
            "attempted",
            "completed",
        ]
    assert "private-token" not in caplog.text
    assert "gitlab_group" not in caplog.text


@pytest.mark.parametrize("cancelled", [False, True])
async def test_redis_errors_and_cancellation_never_log_completion(
    fake_redis: FakeRedis, caplog: pytest.LogCaptureFixture, cancelled: bool
) -> None:
    caplog.set_level(logging.INFO)
    error = asyncio.CancelledError("private-error") if cancelled else RuntimeError("private-error")
    with patch.object(fake_redis, "hset", new=AsyncMock(side_effect=error)):
        with pytest.raises(type(error)):
            await CourseStore(fake_redis).upsert_course("demo", config(), "private-token")
    records = entries(caplog, "storage.write")
    assert [record["outcome"] for record in records] == ["attempted", "unknown" if cancelled else "failed"]
    assert "private-error" not in caplog.text
    assert "private-token" not in caplog.text


async def test_rejected_requests_and_actor_isolation(
    client_with_overrides: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    assert (
        await client_with_overrides.delete("/courses/demo", headers={"Authorization": "Bearer admin-token"})
    ).status_code == 204
    assert (await client_with_overrides.delete("/courses/demo?token=private-query")).status_code == 403
    records = [record for record in entries(caplog, "http.request") if record["outcome"] != "attempted"]
    assert [record["actor"] for record in records] == ["admin_token", "anonymous"]
    assert [record["outcome"] for record in records] == ["returned", "rejected"]
    assert records[0]["request_id"] != records[1]["request_id"]
    assert records[0]["target"] == {"name": "demo"}
    assert "admin-token" not in caplog.text
    assert "private-query" not in json.dumps(records)


async def test_course_token_actor_and_invalid_payload(
    client_with_overrides: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    with respx.mock:
        respx.get("http://manytask.test/api/demo/ping").mock(return_value=httpx.Response(200))
        response = await client_with_overrides.post(
            "/courses/demo", content="[invalid-yaml", headers={"Authorization": "Bearer private-token"}
        )
    assert response.status_code == 422
    records = entries(caplog, "http.request")
    assert records[-1]["actor"] == "course_token"
    assert records[-1]["outcome"] == "rejected"
    assert entries(caplog, "storage.write")[-1]["actor"] == "course_token"
    assert "private-token" not in caplog.text
    assert "[invalid-yaml" not in caplog.text


async def test_each_outbound_score_retry_is_audited(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    client = ManytaskClient("http://manytask.test", retry_attempts=2, retry_backoff_sec=0)
    try:
        with respx.mock:
            respx.post("http://manytask.test/api/demo/report").mock(
                side_effect=[httpx.Response(503, text="private-error"), httpx.Response(200, json={"score": 8})]
            )
            assert (
                await client.report_score("demo", token="private-token", username="student", task="task", score=8) == 8
            )
    finally:
        await client.aclose()
    records = entries(caplog, "storage.write")
    assert [record["outcome"] for record in records] == ["attempted", "failed", "attempted", "completed"]
    assert all(record["target"]["username"] == "student" for record in records)
    assert "private-token" not in caplog.text
    assert "private-error" not in caplog.text


async def test_unhandled_http_error_is_audited(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    app = FastAPI()
    install_request_audit(app)

    @app.post("/write")
    async def fail() -> None:
        set_audit_actor("course_token")
        raise RuntimeError("private-error")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with pytest.raises(RuntimeError):
            await client.post("/write")
    assert [record["outcome"] for record in entries(caplog, "http.request")] == ["attempted", "failed"]
    assert "private-error" not in caplog.text
