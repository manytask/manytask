"""Unit tests for TokenAuthCache (positive-only ping cache in Redis)."""

from __future__ import annotations

from fakeredis.aioredis import FakeRedis

from app.manytask.auth_cache import TokenAuthCache


class TestTokenAuthCache:
    async def test_unknown_token_is_not_cached(self, fake_redis: FakeRedis) -> None:
        cache = TokenAuthCache(fake_redis, ttl_sec=30)
        assert await cache.is_valid("python-101", "tok") is False

    async def test_remember_then_is_valid_true(self, fake_redis: FakeRedis) -> None:
        cache = TokenAuthCache(fake_redis, ttl_sec=30)
        await cache.remember_valid("python-101", "tok")
        assert await cache.is_valid("python-101", "tok") is True

    async def test_isolation_between_courses(self, fake_redis: FakeRedis) -> None:
        cache = TokenAuthCache(fake_redis, ttl_sec=30)
        await cache.remember_valid("python-101", "tok")
        assert await cache.is_valid("go-101", "tok") is False

    async def test_isolation_between_tokens(self, fake_redis: FakeRedis) -> None:
        cache = TokenAuthCache(fake_redis, ttl_sec=30)
        await cache.remember_valid("python-101", "tok-a")
        assert await cache.is_valid("python-101", "tok-b") is False

    async def test_token_value_not_stored_in_plaintext(self, fake_redis: FakeRedis) -> None:
        cache = TokenAuthCache(fake_redis, ttl_sec=30)
        await cache.remember_valid("python-101", "super-secret-token")

        keys = [k async for k in fake_redis.scan_iter(match="auth:ping:*")]
        assert keys, "cache must create at least one key"
        for key in keys:
            assert "super-secret-token" not in (key if isinstance(key, str) else key.decode())

    async def test_ttl_is_set(self, fake_redis: FakeRedis) -> None:
        cache = TokenAuthCache(fake_redis, ttl_sec=30)
        await cache.remember_valid("python-101", "tok")

        keys = [k async for k in fake_redis.scan_iter(match="auth:ping:*")]
        assert keys
        ttl = await fake_redis.ttl(keys[0])
        assert 0 < ttl <= 30
