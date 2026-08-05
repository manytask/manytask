"""Unit tests for ProcessedCommentStore."""

from __future__ import annotations

from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis

from app.storage.processed_store import (
    PROCESSED_TTL_SECONDS,
    ProcessedCommentStore,
)


class TestMarkAndCheck:
    async def test_unknown_comment_is_not_processed(self, fake_redis: FakeRedis) -> None:
        store = ProcessedCommentStore(fake_redis)
        assert await store.is_processed("course-a", "mr-1", "comment-1") is False

    async def test_mark_then_is_processed_true(self, fake_redis: FakeRedis) -> None:
        store = ProcessedCommentStore(fake_redis)
        await store.mark_processed("course-a", "mr-1", "comment-1")
        assert await store.is_processed("course-a", "mr-1", "comment-1") is True

    async def test_mark_is_idempotent(self, fake_redis: FakeRedis) -> None:
        store = ProcessedCommentStore(fake_redis)
        await store.mark_processed("course-a", "mr-1", "comment-1")
        await store.mark_processed("course-a", "mr-1", "comment-1")
        assert await store.is_processed("course-a", "mr-1", "comment-1") is True

    async def test_isolation_between_courses_and_mrs(self, fake_redis: FakeRedis) -> None:
        store = ProcessedCommentStore(fake_redis)
        await store.mark_processed("course-a", "mr-1", "c1")
        assert await store.is_processed("course-b", "mr-1", "c1") is False
        assert await store.is_processed("course-a", "mr-2", "c1") is False


class TestTTL:
    async def test_ttl_set_on_first_mark(self, fake_redis: FakeRedis) -> None:
        store = ProcessedCommentStore(fake_redis)
        await store.mark_processed("course-a", "mr-1", "c1")

        ttl = await fake_redis.ttl("processed:course-a:mr-1")
        assert 0 < ttl <= PROCESSED_TTL_SECONDS

    async def test_ttl_refreshed_on_subsequent_mark(self, fake_redis: FakeRedis) -> None:
        store = ProcessedCommentStore(fake_redis)
        await store.mark_processed("course-a", "mr-1", "c1")

        await fake_redis.expire("processed:course-a:mr-1", 100)
        ttl_before = await fake_redis.ttl("processed:course-a:mr-1")
        assert ttl_before <= 100

        await store.mark_processed("course-a", "mr-1", "c2")

        ttl_after = await fake_redis.ttl("processed:course-a:mr-1")
        assert ttl_after > ttl_before
        assert ttl_after <= PROCESSED_TTL_SECONDS
        assert ttl_after >= PROCESSED_TTL_SECONDS - 5


class TestSurvivesRestart:
    async def test_state_survives_client_replacement(
        self,
        fake_redis_server: FakeServer,
    ) -> None:
        client_a = FakeRedis(server=fake_redis_server, decode_responses=True)
        try:
            store_a = ProcessedCommentStore(client_a)
            await store_a.mark_processed("course-a", "mr-1", "c1")
        finally:
            await client_a.aclose()

        client_b = FakeRedis(server=fake_redis_server, decode_responses=True)
        try:
            store_b = ProcessedCommentStore(client_b)
            assert await store_b.is_processed("course-a", "mr-1", "c1") is True
            await store_b.mark_processed("course-a", "mr-1", "c1")
            assert await store_b.is_processed("course-a", "mr-1", "c1") is True
        finally:
            await client_b.aclose()
