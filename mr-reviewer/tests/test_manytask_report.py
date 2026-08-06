"""Unit tests for ManytaskClient.report_score."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.manytask.client import ManytaskClient
from app.manytask.errors import (
    ManytaskReportRejected,
    ManytaskTokenForbidden,
    ManytaskUnavailable,
)


@pytest.fixture
def client() -> ManytaskClient:
    return ManytaskClient(base_url="http://manytask.test", timeout_sec=1.0)


class TestReportSuccess:
    @respx.mock
    async def test_posts_form_and_returns_final_score(self, client: ManytaskClient) -> None:
        route = respx.post("http://manytask.test/api/python-101/report").mock(
            return_value=httpx.Response(
                200,
                json={"user_id": 5, "username": "stud", "task": "task-1", "score": 350},
            )
        )

        final = await client.report_score(
            "python-101",
            token="course-tok",
            username="stud",
            task="task-1",
            score=350,
        )

        assert final == 350
        assert route.called
        request = route.calls.last.request
        assert request.headers["authorization"] == "Bearer course-tok"
        body = request.content.decode()
        assert "username=stud" in body
        assert "task=task-1" in body
        assert "score=350" in body
        assert "allow_reduction=True" in body
        assert "check_deadline=False" in body


class TestReportErrors:
    @respx.mock
    async def test_403_raises_forbidden(self, client: ManytaskClient) -> None:
        respx.post("http://manytask.test/api/python-101/report").mock(return_value=httpx.Response(403))
        with pytest.raises(ManytaskTokenForbidden):
            await client.report_score("python-101", token="t", username="u", task="x", score=1)

    @respx.mock
    async def test_404_raises_rejected(self, client: ManytaskClient) -> None:
        respx.post("http://manytask.test/api/python-101/report").mock(
            return_value=httpx.Response(404, text="no such user")
        )
        with pytest.raises(ManytaskReportRejected):
            await client.report_score("python-101", token="t", username="ghost", task="x", score=1)

    @respx.mock
    async def test_409_finished_course_raises_rejected(self, client: ManytaskClient) -> None:
        respx.post("http://manytask.test/api/python-101/report").mock(return_value=httpx.Response(409))
        with pytest.raises(ManytaskReportRejected):
            await client.report_score("python-101", token="t", username="u", task="x", score=1)

    @respx.mock
    async def test_500_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.post("http://manytask.test/api/python-101/report").mock(return_value=httpx.Response(500))
        with pytest.raises(ManytaskUnavailable):
            await client.report_score("python-101", token="t", username="u", task="x", score=1)

    @respx.mock
    async def test_timeout_raises_unavailable(self, client: ManytaskClient) -> None:
        respx.post("http://manytask.test/api/python-101/report").mock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(ManytaskUnavailable):
            await client.report_score("python-101", token="t", username="u", task="x", score=1)
