"""Unit tests for CourseStore."""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis

from app.models import CURRENT_SCHEMA_VERSION, CourseConfig
from app.storage.course_store import CourseStore


def _config() -> CourseConfig:
    return CourseConfig.model_validate(
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "gitlab_group": "course/students",
            "tasks": [
                {
                    "name": "task-1",
                    "checklist": [
                        {"type": "pipeline_passed"},
                        {"type": "forbidden_files", "extensions": [".env"]},
                    ],
                }
            ],
        }
    )


class TestUpsertGet:
    async def test_upsert_then_get_round_trip(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        cfg = _config()

        await store.upsert_course("python-101", cfg, course_token="tok-123")

        loaded = await store.get_course("python-101")
        assert loaded is not None
        name, restored_cfg, token = loaded
        assert name == "python-101"
        assert token == "tok-123"
        assert restored_cfg.model_dump() == cfg.model_dump()

    async def test_get_unknown_course_returns_none(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        assert await store.get_course("nope") is None

    async def test_upsert_overwrites_existing(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        await store.upsert_course("c", _config(), course_token="old")
        await store.upsert_course("c", _config(), course_token="new")

        loaded = await store.get_course("c")
        assert loaded is not None
        assert loaded[2] == "new"


class TestList:
    async def test_list_courses_empty(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        assert await store.list_courses() == []

    async def test_list_courses_returns_names_only(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        await store.upsert_course("a", _config(), course_token="t")
        await store.upsert_course("b", _config(), course_token="t")

        names = await store.list_courses()
        assert sorted(names) == ["a", "b"]


class TestDelete:
    async def test_delete_removes_course(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        await store.upsert_course("c", _config(), course_token="t")

        await store.delete_course("c")

        assert await store.get_course("c") is None
        assert await store.list_courses() == []

    async def test_delete_unknown_is_idempotent(self, fake_redis: FakeRedis) -> None:
        store = CourseStore(fake_redis)
        await store.delete_course("never-existed")  # must not raise


class TestSchemaVersionMismatch:
    async def test_get_logs_warning_and_returns_none_on_mismatch(
        self,
        fake_redis: FakeRedis,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await fake_redis.hset(  # type: ignore[misc]
            "courses:legacy",
            mapping={
                "config_json": "{}",
                "course_token": "tok",
                "schema_version": "999",
                "updated_at": "2026-04-26T00:00:00+00:00",
            },
        )
        store = CourseStore(fake_redis)

        with caplog.at_level("WARNING"):
            result = await store.get_course("legacy")

        assert result is None
        assert "schema_version" in caplog.text

    async def test_list_skips_mismatched_when_loading(
        self,
        fake_redis: FakeRedis,
    ) -> None:
        await fake_redis.hset(  # type: ignore[misc]
            "courses:legacy",
            mapping={
                "config_json": "{}",
                "course_token": "tok",
                "schema_version": "999",
                "updated_at": "2026-04-26T00:00:00+00:00",
            },
        )
        store = CourseStore(fake_redis)
        await store.upsert_course("ok", _config(), course_token="t")

        names = await store.list_courses()
        assert "legacy" in names  # list returns names regardless

        # but get_course filters out
        assert await store.get_course("legacy") is None
        assert await store.get_course("ok") is not None
