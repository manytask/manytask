"""Unit tests for SourceCraftApi.

Focus of these tests is the slug construction contract shared between
``check_project_exists`` and ``create_project``: both must derive the repo
slug from the same source (the RMS-native ``RmsUser.username``), otherwise
a user whose auth-provider login differs from their SourceCraft username
(e.g. Yandex login ``Ps5`` but SourceCraft assigns fallback slug ``ps5-1``)
will get a false negative from the existence check and a 500
``SlugIsNotAvailable`` from the follow-up create call.
"""

from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from manytask.abstract import RmsApiException, RmsUser
from manytask.course import ProtectedBranchSettings
from manytask.sourcecraft import SourceCraftApi, SourceCraftConfig

TEST_ORG = "hsemanytask"
TEST_STUDENTS_GROUP = "ami-python-basic-st-26f"
TEST_PUBLIC_REPO = "public-2026-fall"
YANDEX_LOGIN = "Ps5"
SOURCECRAFT_USERNAME = "ps5-1"
TEST_RMS_ID = "rms-uuid-1"
# SourceCraft ignores these; passed to satisfy create_project's signature.
TEST_CI_CONFIG_PATH = f".gitlab-ci.yml@{TEST_PUBLIC_REPO}"
TEST_PROTECTED_BRANCHES = [
    ProtectedBranchSettings(
        name="main", push_access_level="developer", merge_access_level="developer", allow_force_push=True
    )
]
DOMAIN_LOGIN = "anna@example.org"
DOMAIN_SLUG = "anna-example-org"


@pytest.fixture
def sourcecraft_api():
    """Build a SourceCraftApi with the yandex-cloud SDK and IAM-token flow stubbed out."""
    config = SourceCraftConfig(
        base_url="https://sourcecraft.dev",
        api_url="https://api.sourcecraft.tech/",
        org_slug=TEST_ORG,
        oauth_token="fake-oauth-token",
    )
    with patch("manytask.sourcecraft.SDK"):
        api = SourceCraftApi(config)
    with patch.object(SourceCraftApi, "iam_token", new="fake-iam-token"):
        yield api


def _make_response(status_code, json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body if json_body is not None else {}
    return response


@pytest.mark.parametrize("method", ["add_user_to_namespace_group", "remove_user_from_namespace_group"])
def test_namespace_membership_management_is_explicitly_unsupported(
    sourcecraft_api: SourceCraftApi, method: str
) -> None:
    with pytest.raises(NotImplementedError):
        getattr(sourcecraft_api, method)(-1, TEST_RMS_ID)


def test_check_project_exists_returns_true_on_200(sourcecraft_api):
    with patch.object(sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.OK)) as mock_request:
        assert (
            sourcecraft_api.check_project_exists(project_name=SOURCECRAFT_USERNAME, project_group=TEST_STUDENTS_GROUP)
            is True
        )
    mock_request.assert_called_once_with("GET", f"repos/{TEST_ORG}/{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}")


def test_check_project_exists_returns_false_on_404(sourcecraft_api):
    with patch.object(sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.NOT_FOUND)):
        assert (
            sourcecraft_api.check_project_exists(project_name=SOURCECRAFT_USERNAME, project_group=TEST_STUDENTS_GROUP)
            is False
        )


def test_check_project_exists_raises_on_unexpected_status(sourcecraft_api):
    with patch.object(sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.INTERNAL_SERVER_ERROR)):
        with pytest.raises(RmsApiException):
            sourcecraft_api.check_project_exists(project_name=SOURCECRAFT_USERNAME, project_group=TEST_STUDENTS_GROUP)


def test_create_project_slug_derives_from_rms_user_username(sourcecraft_api):
    """The create-repo POST body must use the RMS-native username as the slug."""
    rms_user = RmsUser(id=TEST_RMS_ID, username=SOURCECRAFT_USERNAME, name="Test User")

    def request_side_effect(method, path, **kwargs):
        if method == "GET" and path == f"repos/{TEST_ORG}/{TEST_PUBLIC_REPO}":
            return _make_response(HTTPStatus.OK, {"id": 42})
        if method == "POST" and path == f"orgs/{TEST_ORG}/repos":
            return _make_response(HTTPStatus.CREATED)
        if method == "POST" and path.endswith("/roles"):
            return _make_response(HTTPStatus.OK)
        raise AssertionError(f"unexpected request {method} {path}")

    with patch.object(sourcecraft_api, "_request", side_effect=request_side_effect) as mock_request:
        sourcecraft_api.create_project(
            rms_user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES
        )

    create_calls = [call for call in mock_request.call_args_list if call.args == ("POST", f"orgs/{TEST_ORG}/repos")]
    assert len(create_calls) == 1
    payload = create_calls[0].kwargs["json"]
    expected_slug = f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}"
    assert payload["slug"] == expected_slug
    assert payload["name"] == expected_slug


def test_existence_check_and_create_use_matching_slug(sourcecraft_api):
    """Regression: when Yandex login ("Ps5") differs from SC username ("ps5-1"),
    callers must pass the SC username to ``check_project_exists`` so that the slug
    it looks up matches the slug ``create_project`` would produce. Passing the
    Yandex login instead is a false negative and leads to a duplicate-create 500.
    """
    rms_user = RmsUser(id=TEST_RMS_ID, username=SOURCECRAFT_USERNAME, name="Test User")

    seen_paths = []

    def record_request(method, path, **kwargs):
        seen_paths.append((method, path))
        if method == "GET" and path == f"repos/{TEST_ORG}/{TEST_PUBLIC_REPO}":
            return _make_response(HTTPStatus.OK, {"id": 42})
        if method == "POST" and path == f"orgs/{TEST_ORG}/repos":
            return _make_response(HTTPStatus.CREATED)
        if method == "POST" and path.endswith("/roles"):
            return _make_response(HTTPStatus.OK)
        if method == "GET" and path.startswith(f"repos/{TEST_ORG}/{TEST_STUDENTS_GROUP}-"):
            return _make_response(HTTPStatus.OK)
        raise AssertionError(f"unexpected request {method} {path}")

    with patch.object(sourcecraft_api, "_request", side_effect=record_request):
        # Simulate what create_project (using rms_user.username) would create ...
        sourcecraft_api.create_project(
            rms_user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES
        )
        # ... and then verify that a subsequent existence check with the SAME
        # (SC-native) username hits the same slug.
        assert (
            sourcecraft_api.check_project_exists(project_name=rms_user.username, project_group=TEST_STUDENTS_GROUP)
            is True
        )

    created_slug = f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}"
    assert ("POST", f"orgs/{TEST_ORG}/repos") in seen_paths
    assert ("GET", f"repos/{TEST_ORG}/{created_slug}") in seen_paths
    # And critically: no GET was ever issued for the Yandex-login-based slug.
    assert ("GET", f"repos/{TEST_ORG}/{TEST_STUDENTS_GROUP}-ps5") not in seen_paths
    assert ("GET", f"repos/{TEST_ORG}/{TEST_STUDENTS_GROUP}-{YANDEX_LOGIN.lower()}") not in seen_paths


def test_get_url_for_repo_uses_passed_username(sourcecraft_api):
    """``get_url_for_repo`` derives the URL from the passed username, so callers
    must also pass the RMS-native username to point students at the right repo.
    """
    url = sourcecraft_api.get_url_for_repo(username=SOURCECRAFT_USERNAME, course_students_group=TEST_STUDENTS_GROUP)
    assert url.endswith(f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}")


def test_get_rms_user_by_username_falls_back_to_sourcecraft_lookup(sourcecraft_api):
    """Regression: CI reports the repo slug ('anna-example-org'), which Passport does not know.

    Normalization is not invertible, so the lookup must ask SourceCraft for that name
    instead of giving up, otherwise /report answers 404 for every domain login.
    """
    profile = {"id": TEST_RMS_ID, "username": DOMAIN_SLUG, "display_name": "Anna Example"}

    with patch.object(sourcecraft_api, "_get_cloud_id_by_yandex_login", side_effect=RmsApiException("no such login")):
        with patch.object(
            sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.OK, profile)
        ) as mock_request:
            rms_user = sourcecraft_api.get_rms_user_by_username(DOMAIN_SLUG)

    assert rms_user == RmsUser(id=TEST_RMS_ID, username=DOMAIN_SLUG, name="Anna Example")
    mock_request.assert_called_once_with("GET", f"users/{DOMAIN_SLUG}")


def test_get_rms_user_by_username_normalizes_before_sourcecraft_lookup(sourcecraft_api):
    """The fallback queries GET /users/{user_slug}, so a raw login must be normalized first."""
    profile = {"id": TEST_RMS_ID, "username": DOMAIN_SLUG, "display_name": "Anna Example"}

    with patch.object(sourcecraft_api, "_get_cloud_id_by_yandex_login", side_effect=RmsApiException("passport down")):
        with patch.object(
            sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.OK, profile)
        ) as mock_request:
            sourcecraft_api.get_rms_user_by_username(DOMAIN_LOGIN)

    mock_request.assert_called_once_with("GET", f"users/{DOMAIN_SLUG}")


def test_get_rms_user_by_username_raises_when_both_lookups_fail(sourcecraft_api):
    """Unknown to Passport and to SourceCraft: the caller must still get an RmsApiException."""
    with patch.object(sourcecraft_api, "_get_cloud_id_by_yandex_login", side_effect=RmsApiException("no such login")):
        with patch.object(sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.NOT_FOUND)):
            with pytest.raises(RmsApiException):
                sourcecraft_api.get_rms_user_by_username(DOMAIN_SLUG)


def test_get_rms_user_by_username_prefers_yandex_login(sourcecraft_api):
    """The yandex login stays the primary path: resolving it must not query by the raw name."""
    cloud_id = "cloud-id-1"
    profile = {"id": TEST_RMS_ID, "username": SOURCECRAFT_USERNAME, "display_name": "Test User"}

    with patch.object(sourcecraft_api, "_get_cloud_id_by_yandex_login", return_value=cloud_id):
        with patch.object(
            sourcecraft_api, "_request", return_value=_make_response(HTTPStatus.OK, profile)
        ) as mock_request:
            rms_user = sourcecraft_api.get_rms_user_by_username(YANDEX_LOGIN)

    assert rms_user.username == SOURCECRAFT_USERNAME
    mock_request.assert_called_once_with("GET", f"users/cloud-id:{cloud_id}")


# ---------------------------------------------------------------------------
# Recovery from partial setup: create_project is idempotent and _add_repo_role
# retries on transient errors. See fix/create-project-recovery.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT, HTTPStatus.UNPROCESSABLE_ENTITY])
def test_create_project_is_idempotent_when_repo_already_exists(sourcecraft_api: SourceCraftApi, status: int) -> None:
    """A repeated create_project call after a partial setup must not raise.

    Real-world scenario: first attempt created the repo but the follow-up
    POST /roles failed with 504. On the next call, POST /orgs/.../repos
    returns SlugIsNotAvailable. Accept client-error statuses only after
    verifying that the student repo exists, then let _add_repo_role finish
    the job.
    """
    rms_user = RmsUser(id=TEST_RMS_ID, username=SOURCECRAFT_USERNAME, name="Test User")

    def side_effect(method: str, path: str, **kwargs: Any) -> httpx.Response:
        if method == "GET" and path == f"repos/{TEST_ORG}/{TEST_PUBLIC_REPO}":
            return _make_response(HTTPStatus.OK, {"id": 42})
        if method == "POST" and path == f"orgs/{TEST_ORG}/repos":
            return _make_response(
                status,
                {"error_code": "SlugIsNotAvailable", "message": "slug taken"},
            )
        if method == "GET" and path == f"repos/{TEST_ORG}/{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}":
            return _make_response(HTTPStatus.OK, {"id": 43})
        if method == "POST" and path.endswith("/roles"):
            return _make_response(HTTPStatus.OK)
        raise AssertionError(f"unexpected request {method} {path}")

    with patch.object(sourcecraft_api, "_request", side_effect=side_effect):
        sourcecraft_api.create_project(
            rms_user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES
        )


@pytest.mark.parametrize("status", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT, HTTPStatus.UNPROCESSABLE_ENTITY])
@pytest.mark.parametrize("error_code", ["FailedPrecondition", "UserNotOrganizationMember"])
def test_existing_student_repo_recovery_grants_role_to_invitee(
    sourcecraft_api: SourceCraftApi, status: int, error_code: str
) -> None:
    rms_user = RmsUser(id=TEST_RMS_ID, username=SOURCECRAFT_USERNAME, name="Test User")
    repo_slug = f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}"
    role_subjects: list[dict[str, str]] = []
    invitations: list[dict[str, Any]] = []

    def respond(method: str, path: str, **kwargs: Any) -> httpx.Response:
        if method == "GET" and path == f"repos/{TEST_ORG}/{TEST_PUBLIC_REPO}":
            return httpx.Response(HTTPStatus.OK, json={"id": "template-repo"})
        if method == "POST" and path == f"orgs/{TEST_ORG}/repos":
            return httpx.Response(status, json={"error_code": "SlugIsNotAvailable"})
        if method == "GET" and path == f"repos/{TEST_ORG}/{repo_slug}":
            return httpx.Response(HTTPStatus.OK, json={"id": "student-repo"})
        if method == "POST" and path == f"repos/{TEST_ORG}/{repo_slug}/roles":
            subject = kwargs["json"]["subject_roles"][0]["subject"].copy()
            role_subjects.append(subject)
            if subject["type"] == "user":
                return httpx.Response(HTTPStatus.BAD_REQUEST, json={"error_code": error_code})
            return httpx.Response(HTTPStatus.OK)
        if method == "POST" and path == f"orgs/{TEST_ORG}/invites":
            invitations.append(kwargs["json"])
            return httpx.Response(
                HTTPStatus.ACCEPTED,
                json={"status": "success", "response": {"invites": [{"subject": {"id": "test-invitee"}}]}},
            )
        raise AssertionError(f"Unexpected request {method} {path}")

    with (
        patch.object(sourcecraft_api, "_request", side_effect=respond),
        patch.object(sourcecraft_api, "get_rms_user_by_id", return_value=rms_user) as get_user,
    ):
        sourcecraft_api.create_project(
            rms_user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO, TEST_CI_CONFIG_PATH, TEST_PROTECTED_BRANCHES
        )

    get_user.assert_called_once_with(TEST_RMS_ID)
    assert invitations == [{"invitees": [{"slug": SOURCECRAFT_USERNAME}]}]
    assert role_subjects == [{"type": "user", "id": TEST_RMS_ID}, {"type": "invitee", "id": "test-invitee"}]


def test_add_repo_role_when_role_already_exists_is_a_noop(sourcecraft_api):
    """POST /roles is idempotent on the SourceCraft side: posting a role that
    already exists returns 200 OK, not a duplicate-role error. This lets
    create_project be safely re-invoked (e.g. after a partial setup) without
    a pre-flight GET or duplicate-error handling.
    """
    repo_slug = f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}"

    def side_effect(method, path, **kwargs):
        if method == "POST" and path == f"repos/{TEST_ORG}/{repo_slug}/roles":
            return _make_response(HTTPStatus.OK)
        raise AssertionError(f"unexpected request {method} {path}")

    with patch.object(sourcecraft_api, "_request", side_effect=side_effect):
        # Must not raise even when role already exists on SC side.
        sourcecraft_api._add_repo_role(repo_slug, "developer", TEST_RMS_ID)


def test_add_repo_role_retries_on_gateway_timeout(sourcecraft_api):
    """504 from POST /roles must trigger transparent retry within the same call.

    Motivated by production incident: SC returned one 504 during a real
    student sign-up, manytask propagated the error, and the student's repo
    was left permanently without a developer-role assignment because no
    retry mechanism existed.
    """
    repo_slug = f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}"
    responses = iter(
        [
            _make_response(HTTPStatus.GATEWAY_TIMEOUT, {"error_code": "GatewayTimeout"}),
            _make_response(HTTPStatus.OK),
        ]
    )

    def side_effect(method, path, **kwargs):
        if method == "POST" and path == f"repos/{TEST_ORG}/{repo_slug}/roles":
            return next(responses)
        raise AssertionError(f"unexpected request {method} {path}")

    with (
        patch.object(sourcecraft_api, "_request", side_effect=side_effect),
        patch("tenacity.nap.sleep"),  # no real sleep in tests
    ):
        # Must not raise — second attempt succeeds.
        sourcecraft_api._add_repo_role(repo_slug, "developer", TEST_RMS_ID)


def test_add_repo_role_does_not_retry_on_client_error(sourcecraft_api):
    """4xx from POST /roles must fail immediately without retry.

    Retrying a 400 Bad Request would just waste time — the request is
    malformed, retrying with the same payload cannot succeed.
    """
    repo_slug = f"{TEST_STUDENTS_GROUP}-{SOURCECRAFT_USERNAME}"
    call_count = {"n": 0}

    def side_effect(method, path, **kwargs):
        if method == "POST" and path == f"repos/{TEST_ORG}/{repo_slug}/roles":
            call_count["n"] += 1
            return _make_response(HTTPStatus.BAD_REQUEST, {"error_code": "BadRequest"})
        raise AssertionError(f"unexpected request {method} {path}")

    with (
        patch.object(sourcecraft_api, "_request", side_effect=side_effect),
        patch("tenacity.nap.sleep"),
    ):
        with pytest.raises(RmsApiException):
            sourcecraft_api._add_repo_role(repo_slug, "developer", TEST_RMS_ID)

    assert call_count["n"] == 1, "4xx must not be retried"


@pytest.mark.parametrize("status", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT, HTTPStatus.UNPROCESSABLE_ENTITY])
def test_public_repo_creation_reuses_verified_existing_slug(sourcecraft_api: SourceCraftApi, status: int) -> None:
    repo_slug = "existing-public"
    repo_path = f"repos/{TEST_ORG}/{repo_slug}"
    responses = [
        httpx.Response(status, json={"error_code": "SlugIsNotAvailable", "message": "slug unavailable"}),
        httpx.Response(HTTPStatus.OK, json={"id": "existing-repo", "slug": repo_slug}),
        httpx.Response(HTTPStatus.OK),
    ]
    with patch.object(sourcecraft_api, "_request", side_effect=responses) as request:
        sourcecraft_api.create_public_repo("unused", repo_slug)
    assert [call.args for call in request.call_args_list] == [
        ("POST", f"orgs/{TEST_ORG}/repos"),
        ("GET", repo_path),
        ("PATCH", f"{TEST_ORG}/{repo_slug}"),
    ]
    assert request.call_args.kwargs["json"] == {"template_type": "organizational"}


@pytest.mark.parametrize("status", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT])
@pytest.mark.parametrize("lookup_status", [HTTPStatus.NOT_FOUND, HTTPStatus.FORBIDDEN, HTTPStatus.SERVICE_UNAVAILABLE])
def test_unavailable_slug_is_not_reused_without_existing_repo(
    sourcecraft_api: SourceCraftApi, status: int, lookup_status: int
) -> None:
    responses = [
        httpx.Response(status, json={"error_code": "SlugIsNotAvailable", "message": "slug unavailable"}),
        httpx.Response(lookup_status),
    ]
    with patch.object(sourcecraft_api, "_request", side_effect=responses) as request:
        with pytest.raises(RmsApiException, match="SlugIsNotAvailable"):
            sourcecraft_api.create_public_repo("unused", "unavailable-public")
    assert [call.args[0] for call in request.call_args_list] == ["POST", "GET"]


@pytest.mark.parametrize(
    ("status", "error_code"),
    [
        (HTTPStatus.BAD_REQUEST, "InvalidArgument"),
        (HTTPStatus.CONFLICT, "OtherConflict"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "SlugIsNotAvailable"),
    ],
)
def test_other_creation_errors_are_not_treated_as_existing_repositories(
    sourcecraft_api: SourceCraftApi, status: int, error_code: str
) -> None:
    response = httpx.Response(status, json={"error_code": error_code})
    with patch.object(sourcecraft_api, "_request", return_value=response) as request:
        with pytest.raises(RmsApiException, match=error_code):
            sourcecraft_api.create_public_repo("unused", "failed-public")
    request.assert_called_once()
