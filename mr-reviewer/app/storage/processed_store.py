"""Tracks already-handled score comments per (course, MR) in Redis."""

from __future__ import annotations

from redis.asyncio import Redis

PROCESSED_TTL_SECONDS: int = 60 * 24 * 60 * 60  # 60 days


class ProcessedCommentStore:
    """Idempotency set of comment IDs per (course, MR), with sliding TTL.

    Key: ``processed:<course>:<mr_id>`` — Redis SET of ``comment_id`` strings.
    TTL: refreshed on every ``mark_processed`` call (sliding window).
    """

    KEY_PREFIX = "processed:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @classmethod
    def _key(cls, course: str, mr_id: str) -> str:
        return f"{cls.KEY_PREFIX}{course}:{mr_id}"

    async def mark_processed(self, course: str, mr_id: str, comment_id: str) -> None:
        key = self._key(course, mr_id)
        async with self._redis.pipeline(transaction=False) as pipe:
            pipe.sadd(key, comment_id)
            pipe.expire(key, PROCESSED_TTL_SECONDS)
            await pipe.execute()

    async def is_processed(self, course: str, mr_id: str, comment_id: str) -> bool:
        return bool(await self._redis.sismember(self._key(course, mr_id), comment_id))  # type: ignore[misc]
