"""Namespace membership operations must distinguish missing access from RMS failures."""

from collections.abc import Iterator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from gitlab import GitlabGetError, const

from manytask.glab import GitLabApi, GitLabConfig
from tests.constants import TEST_GROUP_ID, TEST_USER_ID


@pytest.fixture
def namespace_gitlab() -> Iterator[tuple[GitLabApi, MagicMock]]:
    with patch("manytask.glab.gitlab.Gitlab") as backend:
        yield GitLabApi(GitLabConfig("https://gitlab.example", "test-token")), backend.return_value


@pytest.mark.parametrize("operation", ["add", "remove"])
@pytest.mark.parametrize("status", [HTTPStatus.FORBIDDEN, HTTPStatus.SERVICE_UNAVAILABLE])
def test_namespace_membership_lookup_failure_is_not_treated_as_absent(
    namespace_gitlab, operation: str, status: HTTPStatus
) -> None:
    api, client = namespace_gitlab
    group = client.groups.get.return_value
    group.members.get.side_effect = GitlabGetError("Lookup failed", response_code=status)

    with pytest.raises(RuntimeError, match="Lookup failed"):
        getattr(
            api, f"{operation}_user_to_namespace_group" if operation == "add" else "remove_user_from_namespace_group"
        )(TEST_GROUP_ID, str(TEST_USER_ID))

    group.members.create.assert_not_called()
    group.members.delete.assert_not_called()


@pytest.mark.parametrize("operation", ["add", "remove"])
def test_namespace_membership_not_found_is_retryable(namespace_gitlab, operation: str) -> None:
    api, client = namespace_gitlab
    group = client.groups.get.return_value
    group.members.get.side_effect = GitlabGetError("Missing member", response_code=HTTPStatus.NOT_FOUND)
    method = api.add_user_to_namespace_group if operation == "add" else api.remove_user_from_namespace_group

    method(TEST_GROUP_ID, str(TEST_USER_ID))

    if operation == "add":
        group.members.create.assert_called_once_with(
            {"user_id": TEST_USER_ID, "access_level": const.AccessLevel.MAINTAINER}
        )
    else:
        group.members.delete.assert_not_called()
