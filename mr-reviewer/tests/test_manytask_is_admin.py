"""Unit tests for ManytaskClient.is_admin."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.manytask.client import ManytaskClient
from app.manytask.errors import ManytaskTokenForbidden, ManytaskUnavailable


@pytest.fixture
def client() -> ManytaskClient:
    return ManytaskClient(base_url="http://manytask.test", timeout_sec=1.0)


class TestIsAdmin:
    @respx.mock
    async def test_true(self, client: ManytaskClient) -> None:
        route = respx.get("http://manytask.test/api/python-101/is_admin").mock(
            return_value=httpx.Response(200, json={"rms_username": "teacher", "is_admin": True})
        )
        result = await client.is_admin("python-101", token="tok", rms_username="teacher")
        assert result is True
        assert route.calls.last.request.url.params["rms_username"] == "teacher"
        assert route.calls.last.request.headers["authorization"] == "Bearer tok"

    @respx.mock
    async def test_false_for_unknown_user(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/is_admin").mock(
            return_value=httpx.Response(200, json={"rms_username": "ghost", "is_admin": False})
        )
        assert await client.is_admin("python-101", token="tok", rms_username="ghost") is False

    @respx.mock
    async def test_403_raises_forbidden(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/is_admin").mock(return_value=httpx.Response(403))
        with pytest.raises(ManytaskTokenForbidden):
            await client.is_admin("python-101", token="bad", rms_username="x")

    @respx.mock
    async def test_500_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/is_admin").mock(return_value=httpx.Response(500))
        with pytest.raises(ManytaskUnavailable):
            await client.is_admin("python-101", token="t", rms_username="x")

    @respx.mock
    async def test_timeout_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/is_admin").mock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(ManytaskUnavailable):
            await client.is_admin("python-101", token="t", rms_username="x")
