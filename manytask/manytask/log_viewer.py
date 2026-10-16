"""Bounded reads of the log files shared by the Gunicorn workers."""

import os
from pathlib import Path

LOG_FILES = {name: Path(f"/var/log/{name}.log") for name in ("general", "error", "access")}
MAX_LOG_BYTES = 64 * 1024
MAX_LOG_LINES = 200


def read_log_tail(source: str) -> str:
    """Read a snapshot, reopening each time to tolerate rotation and truncation.

    Only allowlisted sources are accepted. Bound both disk reads and the response,
    even when a single log line is unusually large.
    """
    with LOG_FILES[source].open("rb") as log_file:
        size = log_file.seek(0, os.SEEK_END)
        start = max(0, size - MAX_LOG_BYTES)
        log_file.seek(start)
        content = log_file.read(min(size, MAX_LOG_BYTES))
    if start:
        # Discard a line (or UTF-8 character) cut off by the byte limit.
        content = content.partition(b"\n")[2]
    return "\n".join(content.decode("utf-8", errors="replace").splitlines()[-MAX_LOG_LINES:])
