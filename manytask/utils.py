from __future__ import annotations

from datetime import datetime
from typing import Any


def sanitize_log_value(value: Any) -> str:
    """Sanitize values for logging to prevent log injection.

    Handles common types and ensures the output is a safe string representation.

    Args:
        value: Any value that needs to be sanitized for logging

    Returns:
        A safe string representation of the value, with newlines escaped and length limited
    """
    if value is None:
        return "None"
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value).replace("\n", "\\n")[:1000]
