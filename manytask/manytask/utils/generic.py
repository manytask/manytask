import html
import logging
import re
import secrets
from http import HTTPStatus
from typing import Any, Callable

from authlib.integrations.base_client import OAuthError
from flask import session
from requests import Response
from requests.exceptions import HTTPError
from sqlalchemy.exc import NoResultFound

logger = logging.getLogger(__name__)


def sanitize_log_data(data: str | None) -> str | None:
    """Sanitize form data."""
    if data is None:
        return None
    sanitized_data = data.replace("\r", "").replace("\n", "")
    return sanitized_data


def generate_token_hex(bytes_count: int = 24) -> str:
    return secrets.token_hex(nbytes=bytes_count)


def lerp(p1: tuple[float, float], p2: tuple[float, float], x: float) -> float:
    t = (x - p1[0]) / (p2[0] - p1[0])
    return p1[1] * (1 - t) + p2[1] * t


def validate_name(name: str) -> str | None:
    return name if (re.match(r"^[a-zA-Zа-яА-Я-]{1,50}$", name) is not None) else None


def sanitize_and_validate_comment(comment: str | None, max_length: int = 1000) -> tuple[str | None, str | None]:
    if not comment:
        return None, None
    comment = comment.strip()
    if len(comment) > max_length:
        return None, f"Comment is too long (maximum {max_length} characters)"

    printable_chars_first_idx = 32
    cleaned = "".join(
        char for char in comment if char in "\n\t" or (ord(char) >= printable_chars_first_idx and char.isprintable())
    )

    sanitized = re.sub(r"\n{3,}", "\n\n", html.escape(cleaned)).strip()

    if not sanitized:
        return None, None

    return sanitized, None


def check_course_creation_namespace_permission(
    storage_api: Any,
    namespace_id: int,
    username: str,
    is_instance_admin: bool,
) -> tuple[Any, str | None, str | None, int | None]:
    namespace = None
    role = None
    if namespace_id == 0:
        if not is_instance_admin:
            logger.warning("User %s attempted to create course without namespace", username)
            return None, None, "Only Instance Admin can create courses without namespace", HTTPStatus.FORBIDDEN
    else:
        try:
            namespace, role = storage_api.get_namespace_by_id(namespace_id, username)
        except (PermissionError, NoResultFound):
            logger.warning(
                "User %s attempted to create course in inaccessible namespace id=%s", username, namespace_id
            )
            return None, None, "Namespace not found or access denied", HTTPStatus.NOT_FOUND

        if not is_instance_admin and role != "namespace_admin":
            logger.warning(
                "User %s with role %s attempted to create course in namespace id=%s",
                username,
                role,
                namespace_id,
            )
            return (
                None,
                None,
                "Only Instance Admin or Namespace Admin can create courses",
                HTTPStatus.FORBIDDEN,
            )

    return namespace, role, None, None


def check_oauth_authenticated(
    make_auth_request: Callable[[str], Response],
    refresh_token_fn: Callable[[], dict | None],
    oauth_access_token: str,
    oauth_refresh_token: str,
    log_prefix: str = "",
) -> bool:
    response = make_auth_request(oauth_access_token)

    try:
        response.raise_for_status()
        return True
    except HTTPError as e:
        if e.response.status_code == HTTPStatus.UNAUTHORIZED:
            try:
                logger.info("%sAccess token expired. Trying to refresh token.", log_prefix)

                new_tokens = refresh_token_fn()
                if not new_tokens:
                    return False

                new_access = new_tokens.get("access_token", "")
                new_refresh = new_tokens.get("refresh_token", oauth_refresh_token)

                response = make_auth_request(new_access)
                response.raise_for_status()

                session["auth"].update({"access_token": new_access, "refresh_token": new_refresh})
                logger.info("%sToken refreshed successfully.", log_prefix)

                return True
            except (HTTPError, OAuthError):
                logger.error("Failed to refresh %stoken", log_prefix, exc_info=True)
                return False

        logger.info("User is not logged in: %s", e, exc_info=True)
        return False
