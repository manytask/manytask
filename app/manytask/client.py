"""HTTP client for the manytask service."""

from __future__ import annotations

import httpx

from app.manytask.errors import (
    ManytaskCourseNotFound,
    ManytaskReportRejected,
    ManytaskTokenForbidden,
    ManytaskUnavailable,
)
from app.manytask.models import DeadlineEntry, parse_manytask_datetime


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

    async def report_score(
        self,
        course_name: str,
        *,
        token: str,
        username: str,
        task: str,
        score: int,
        allow_reduction: bool = True,
        check_deadline: bool = False,
    ) -> int:
        """Report ``score`` for ``username`` on ``task`` via ``POST /api/<course>/report``.

        ``allow_reduction=True`` + ``check_deadline=False`` make a teacher override
        authoritative: it is not capped by a previous score and not multiplied by the
        deadline penalty (the teacher already decided the grade manually).

        Returns the final stored score. Raises:
            ManytaskTokenForbidden: 403.
            ManytaskReportRejected: terminal 4xx (unknown user/task, finished course).
            ManytaskUnavailable: transport error / 5xx.
        """

        form = {
            "username": username,
            "task": task,
            "score": str(score),
            "allow_reduction": "True" if allow_reduction else "False",
            "check_deadline": "True" if check_deadline else "False",
        }
        try:
            response = await self._client.post(
                f"/api/{course_name}/report",
                data=form,
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 200:
            return int(response.json()["score"])
        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        if 400 <= response.status_code < 500:
            raise ManytaskReportRejected(f"manytask /report rejected ({response.status_code}): {response.text[:200]}")
        raise ManytaskUnavailable(f"manytask /report returned {response.status_code}: {response.text[:200]}")

    async def is_admin(self, course_name: str, *, token: str, rms_username: str) -> bool:
        """Return whether ``rms_username`` is a course admin in manytask.

        Calls ``GET /api/<course>/is_admin?rms_username=X``. The deployed manytask
        endpoint (EDUCATION-59063 / manytask#941) keys on ``rms_username`` and returns
        ``{"rms_username": str, "is_admin": bool}`` with 200 even for unknown users.
        """

        try:
            response = await self._client.get(
                f"/api/{course_name}/is_admin",
                params={"rms_username": rms_username},
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 200:
            return bool(response.json()["is_admin"])
        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        raise ManytaskUnavailable(f"manytask /is_admin returned {response.status_code}: {response.text[:200]}")

    async def get_deadlines(self, course_name: str, *, token: str) -> list[DeadlineEntry]:
        """Fetch the machine-readable deadline list via ``GET /api/<course>/deadlines``."""

        try:
            response = await self._client.get(
                f"/api/{course_name}/deadlines",
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        if response.status_code != 200:
            raise ManytaskUnavailable(f"manytask /deadlines returned {response.status_code}: {response.text[:200]}")

        payload = response.json()
        return [
            DeadlineEntry(
                task_name=item["task_name"],
                group=item["group"],
                deadline=parse_manytask_datetime(item["deadline"]),
                score=int(item["score"]),
                is_bonus=bool(item["is_bonus"]),
                is_large=bool(item["is_large"]),
            )
            for item in payload["tasks"]
        ]
