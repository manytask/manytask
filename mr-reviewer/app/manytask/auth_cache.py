"""Positive-only Redis cache for ManytaskClient.ping results.

We never cache failure: after manytask says "no" once, the next call MUST hit the
real API again, otherwise a transient 5xx would lock a course out for the TTL.
"""

from __future__ import annotations

import hashlib

from redis.asyncio import Redis


class TokenAuthCache:
    """Cache validated (course, token) pairs in Redis with a short TTL.

    Key: ``auth:ping:<course>:<sha256(token)>``; value: literal ``"ok"``.
    The token is hashed so a Redis dump never leaks course tokens.
    """

    KEY_PREFIX = "auth:ping:"

    def __init__(self, redis: Redis, ttl_sec: int) -> None:
        self._redis = redis
        self._ttl = ttl_sec

    @classmethod
    def _key(cls, course: str, token: str) -> str:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"{cls.KEY_PREFIX}{course}:{digest}"

    async def is_valid(self, course: str, token: str) -> bool:
        return await self._redis.exists(self._key(course, token)) > 0  # type: ignore[no-any-return]

    async def remember_valid(self, course: str, token: str) -> None:
        await self._redis.set(self._key(course, token), "ok", ex=self._ttl)
