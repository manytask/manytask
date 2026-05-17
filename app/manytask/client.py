"""HTTP client for the manytask service."""

from __future__ import annotations

import httpx

from app.manytask.errors import (
    ManytaskCourseNotFound,
    ManytaskTokenForbidden,
    ManytaskUnavailable,
)


class ManytaskClient:
    """Async manytask API wrapper. Owns no shared state besides the httpx client."""

    def __init__(self, base_url: str, timeout_sec: float = 5.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_sec,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ping(self, course_name: str, token: str) -> None:
        """Validate ``token`` against ``course_name`` via ``GET /api/<course>/ping``.

        Returns silently on 200. Maps response into typed errors otherwise.
        """

        try:
            response = await self._client.get(
                f"/api/{course_name}/ping",
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 200:
            return
        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        if response.status_code == 404:
            raise ManytaskCourseNotFound(f"manytask does not know course {course_name}")
        raise ManytaskUnavailable(f"manytask /ping returned {response.status_code}: {response.text[:200]}")
