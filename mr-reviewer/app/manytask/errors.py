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


class ManytaskReportRejected(ManytaskError):
    """Manytask rejected the report with a terminal 4xx (bad task/user/finished course).

    Distinct from :class:`ManytaskUnavailable` (transient): a rejected report must
    NOT be retried — the worker marks the comment processed and moves on.
    """
