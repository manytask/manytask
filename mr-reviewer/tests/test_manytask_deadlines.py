"""Unit tests for ManytaskClient.get_deadlines."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.manytask.client import ManytaskClient
from app.manytask.errors import ManytaskTokenForbidden, ManytaskUnavailable


@pytest.fixture
def client() -> ManytaskClient:
    return ManytaskClient(base_url="http://manytask.test", timeout_sec=1.0)


class TestGetDeadlines:
    @respx.mock
    async def test_parses_entries(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/deadlines").mock(
            return_value=httpx.Response(
                200,
                json={
                    "course": "python-101",
                    "tasks": [
                        {
                            "task_name": "task-1",
                            "group": "g0",
                            "deadline": "2030-05-01T23:59:00+00:00",
                            "score": 100,
                            "is_bonus": False,
                            "is_large": True,
                        }
                    ],
                },
            )
        )

        entries = await client.get_deadlines("python-101", token="tok")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.task_name == "task-1"
        assert entry.group == "g0"
        assert entry.deadline == datetime(2030, 5, 1, 23, 59, tzinfo=timezone.utc)
        assert entry.score == 100
        assert entry.is_large is True

    @respx.mock
    async def test_tolerates_trailing_z(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/deadlines").mock(
            return_value=httpx.Response(
                200,
                json={
                    "course": "python-101",
                    "tasks": [
                        {
                            "task_name": "t",
                            "group": "g",
                            "deadline": "2030-05-01T23:59:00Z",
                            "score": 1,
                            "is_bonus": False,
                            "is_large": False,
                        }
                    ],
                },
            )
        )
        entries = await client.get_deadlines("python-101", token="tok")
        assert entries[0].deadline == datetime(2030, 5, 1, 23, 59, tzinfo=timezone.utc)

    @respx.mock
    async def test_403_raises_forbidden(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/deadlines").mock(return_value=httpx.Response(403))
        with pytest.raises(ManytaskTokenForbidden):
            await client.get_deadlines("python-101", token="bad")

    @respx.mock
    async def test_500_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.get("http://manytask.test/api/python-101/deadlines").mock(return_value=httpx.Response(500))
        with pytest.raises(ManytaskUnavailable):
            await client.get_deadlines("python-101", token="t")
