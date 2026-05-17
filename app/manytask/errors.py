"""Typed errors for the manytask client."""

from __future__ import annotations


class ManytaskError(Exception):
    """Base class for manytask client errors."""


class ManytaskTokenForbidden(ManytaskError):
    """The course token is not accepted by manytask (HTTP 403)."""


class ManytaskCourseNotFound(ManytaskError):
    """Manytask does not know this course (HTTP 404)."""


class ManytaskUnavailable(ManytaskError):
    """Manytask is unreachable or returned 5xx — treat as transient outage."""
