"""HTTP authorization helpers for the courses API.

Two flavours:
- ``verify_course_token``: per-course Bearer token; validated against manytask /ping
  with a short positive Redis cache. The validated token is returned, so handlers
  can pass it through into ``CourseStore``.
- ``verify_admin_token``: shared platform-level Bearer token compared against
  ``Settings.admin_token``. Used only by debug endpoints like ``GET /courses``.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from loguru import logger

from app.api.dependencies import (
    get_auth_cache,
    get_manytask_client,
    get_settings_dep,
)
from app.config import Settings
from app.manytask import (
    ManytaskClient,
    ManytaskCourseNotFound,
    ManytaskTokenForbidden,
    ManytaskUnavailable,
    TokenAuthCache,
)


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="empty bearer token")
    return token


async def verify_course_token(
    name: str,
    request: Request,
    manytask: ManytaskClient = Depends(get_manytask_client),  # noqa: B008
    cache: TokenAuthCache = Depends(get_auth_cache),  # noqa: B008
) -> str:
    token = _extract_bearer(request)

    if await cache.is_valid(name, token):
        return token

    try:
        await manytask.ping(name, token)
    except ManytaskTokenForbidden:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"token not authorized for course '{name}'",
        ) from None
    except ManytaskCourseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"manytask does not know course '{name}'",
        ) from None
    except ManytaskUnavailable as err:
        logger.warning("manytask /ping unavailable: {}", err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="manytask is unavailable; please retry later",
        ) from None

    await cache.remember_valid(name, token)
    return token


def verify_admin_token(
    request: Request,
    settings: Settings = Depends(get_settings_dep),  # noqa: B008
) -> None:
    token = _extract_bearer(request)
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin token required")


async def verify_course_or_admin_token(
    name: str,
    request: Request,
    manytask: ManytaskClient = Depends(get_manytask_client),  # noqa: B008
    cache: TokenAuthCache = Depends(get_auth_cache),  # noqa: B008
    settings: Settings = Depends(get_settings_dep),  # noqa: B008
) -> str:
    token = _extract_bearer(request)

    if settings.admin_token and token == settings.admin_token:
        return token

    if await cache.is_valid(name, token):
        return token

    try:
        await manytask.ping(name, token)
    except ManytaskTokenForbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="token not authorized") from None
    except ManytaskCourseNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="course not in manytask") from None
    except ManytaskUnavailable as err:
        logger.warning("manytask /ping unavailable: {}", err)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="manytask unavailable") from None

    await cache.remember_valid(name, token)
    return token
