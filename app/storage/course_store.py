"""Persistence of course configs in Redis."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from redis.asyncio import Redis

from app.models import CURRENT_SCHEMA_VERSION, CourseConfig


class CourseStore:
    """Stores per-course config + token in a Redis HASH per course.

    Key: ``courses:<name>``
    Fields: ``config_json``, ``course_token``, ``schema_version``, ``updated_at``.
    """

    KEY_PREFIX = "courses:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @classmethod
    def _key(cls, name: str) -> str:
        return f"{cls.KEY_PREFIX}{name}"

    async def upsert_course(
        self,
        name: str,
        config: CourseConfig,
        course_token: str,
    ) -> None:
        await self._redis.hset(  # type: ignore[misc]
            self._key(name),
            mapping={
                "config_json": config.model_dump_json(),
                "course_token": course_token,
                "schema_version": str(config.schema_version),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def get_course(self, name: str) -> tuple[str, CourseConfig, str] | None:
        """Return (name, config, course_token) or None if missing/incompatible."""

        data = await self._redis.hgetall(self._key(name))  # type: ignore[misc]
        if not data:
            return None

        try:
            stored_version = int(data.get("schema_version", "-1"))
        except ValueError:
            stored_version = -1

        if stored_version != CURRENT_SCHEMA_VERSION:
            logger.warning(
                "Skipping course {} due to incompatible schema_version (stored={}, current={})",
                name,
                stored_version,
                CURRENT_SCHEMA_VERSION,
            )
            return None

        config = CourseConfig.model_validate_json(data["config_json"])
        return name, config, data["course_token"]

    async def list_courses(self) -> list[str]:
        """Return all course names. Schema-version filtering is per-get."""

        names: list[str] = []
        async for raw_key in self._redis.scan_iter(match=f"{self.KEY_PREFIX}*"):
            key = raw_key if isinstance(raw_key, str) else raw_key.decode()
            names.append(key.removeprefix(self.KEY_PREFIX))
        return names

    async def delete_course(self, name: str) -> None:
        await self._redis.delete(self._key(name))
