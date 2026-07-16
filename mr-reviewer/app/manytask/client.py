"""HTTP client for the manytask service."""

from __future__ import annotations

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.manytask.errors import (
    ManytaskCourseNotFound,
    ManytaskReportRejected,
    ManytaskTokenForbidden,
    ManytaskUnavailable,
)
from app.manytask.models import DeadlineEntry, parse_manytask_datetime
from app.observability import Metrics


class ManytaskClient:
    """Async manytask API wrapper. Owns no shared state besides the httpx client.

    Transient failures (transport errors / 5xx -> ``ManytaskUnavailable``) are
    retried with exponential backoff; each failed attempt increments
    ``manytask_errors_total{endpoint}``. Terminal errors (403/404/4xx) are not
    retried and not counted as availability errors.
    """

    def __init__(
        self,
        base_url: str,
        timeout_sec: float = 5.0,
        *,
        metrics: Metrics | None = None,
        retry_attempts: int = 1,
        retry_backoff_sec: float = 0.5,
        retry_max_backoff_sec: float = 5.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_sec,
        )
        self._metrics = metrics
        self._retrying = AsyncRetrying(
            stop=stop_after_attempt(max(1, retry_attempts)),
            wait=wait_exponential(multiplier=retry_backoff_sec, max=retry_max_backoff_sec),
            retry=retry_if_exception_type(ManytaskUnavailable),
            reraise=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _record_error(self, endpoint: str) -> None:
        if self._metrics is not None:
            self._metrics.record_manytask_error(endpoint)

    async def ping(self, course_name: str, token: str) -> None:
        await self._retrying(self._ping_once, course_name, token)

    async def _ping_once(self, course_name: str, token: str) -> None:
        try:
            response = await self._client.get(
                f"/api/{course_name}/ping",
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            self._record_error("ping")
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 200:
            return
        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        if response.status_code == 404:
            raise ManytaskCourseNotFound(f"manytask does not know course {course_name}")
        self._record_error("ping")
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
        """Default ``allow_reduction=True`` + ``check_deadline=False`` make a teacher
        override authoritative: not capped by a previous score and not multiplied by
        the deadline penalty — the teacher already decided the grade.
        """
        return await self._retrying(
            self._report_score_once,
            course_name,
            token,
            username,
            task,
            score,
            allow_reduction,
            check_deadline,
        )

    async def _report_score_once(
        self,
        course_name: str,
        token: str,
        username: str,
        task: str,
        score: int,
        allow_reduction: bool,
        check_deadline: bool,
    ) -> int:
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
            self._record_error("report")
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 200:
            return int(response.json()["score"])
        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        if 400 <= response.status_code < 500:
            raise ManytaskReportRejected(f"manytask /report rejected ({response.status_code}): {response.text[:200]}")
        self._record_error("report")
        raise ManytaskUnavailable(f"manytask /report returned {response.status_code}: {response.text[:200]}")

    async def is_admin(self, course_name: str, *, token: str, rms_username: str) -> bool:
        return await self._retrying(self._is_admin_once, course_name, token, rms_username)

    async def _is_admin_once(self, course_name: str, token: str, rms_username: str) -> bool:
        try:
            response = await self._client.get(
                f"/api/{course_name}/is_admin",
                params={"rms_username": rms_username},
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            self._record_error("is_admin")
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 200:
            return bool(response.json()["is_admin"])
        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        self._record_error("is_admin")
        raise ManytaskUnavailable(f"manytask /is_admin returned {response.status_code}: {response.text[:200]}")

    async def get_deadlines(self, course_name: str, *, token: str) -> list[DeadlineEntry]:
        return await self._retrying(self._get_deadlines_once, course_name, token)

    async def _get_deadlines_once(self, course_name: str, token: str) -> list[DeadlineEntry]:
        try:
            response = await self._client.get(
                f"/api/{course_name}/deadlines",
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as err:
            self._record_error("deadlines")
            raise ManytaskUnavailable(str(err)) from err

        if response.status_code == 403:
            raise ManytaskTokenForbidden(f"manytask rejected token for course {course_name}")
        if response.status_code != 200:
            self._record_error("deadlines")
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
