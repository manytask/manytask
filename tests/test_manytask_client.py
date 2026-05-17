"""Unit tests for ManytaskClient.ping."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.manytask.client import ManytaskClient
from app.manytask.errors import (
    ManytaskCourseNotFound,
    ManytaskTokenForbidden,
    ManytaskUnavailable,
)


@pytest.fixture
async def client() -> ManytaskClient:
    return ManytaskClient(base_url="http://manytask.test", timeout_sec=1.0)


class TestPingSuccess:
    @respx.mock  # type: ignore[misc]
    async def test_ping_200_returns_silently(self, client: ManytaskClient) -> None:
        route = respx.get("http://manytask.test/api/python-101/ping").mock(
            return_value=httpx.Response(
                200,
                json={"course": "python-101", "ok": True},
            )
        )

        await client.ping("python-101", token="tok-good")

        assert route.called
        sent_auth = route.calls.last.request.headers.get("authorization")
        assert sent_auth == "Bearer tok-good"


class TestPingErrors:
    @respx.mock  # type: ignore[misc]
    async def test_403_raises_forbidden(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/ping").mock(return_value=httpx.Response(403))

        with pytest.raises(ManytaskTokenForbidden):
            await client.ping("python-101", token="tok-bad")

    @respx.mock  # type: ignore[misc]
    async def test_404_raises_course_not_found(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/no-such/ping").mock(return_value=httpx.Response(404))

        with pytest.raises(ManytaskCourseNotFound):
            await client.ping("no-such", token="tok")

    @respx.mock  # type: ignore[misc]
    async def test_500_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/ping").mock(return_value=httpx.Response(500, text="boom"))

        with pytest.raises(ManytaskUnavailable):
            await client.ping("python-101", token="tok")

    @respx.mock  # type: ignore[misc]
    async def test_timeout_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/ping").mock(side_effect=httpx.TimeoutException("slow"))

        with pytest.raises(ManytaskUnavailable):
            await client.ping("python-101", token="tok")

    @respx.mock  # type: ignore[misc]
    async def test_connect_error_raises_unavailable(
        self,
        client: ManytaskClient,
    ) -> None:
        respx.get("http://manytask.test/api/python-101/ping").mock(side_effect=httpx.ConnectError("nope"))

        with pytest.raises(ManytaskUnavailable):
            await client.ping("python-101", token="tok")
