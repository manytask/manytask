"""Bounded reads of the log files shared by the Gunicorn workers."""

import os
from pathlib import Path
from tempfile import TemporaryFile
from typing import BinaryIO

LOG_FILES = {name: Path(f"/var/log/{name}.log") for name in ("general", "error", "access")}
MAX_LOG_BYTES = 1024 * 1024
DEFAULT_LOG_LINES = 200
LOG_LINE_OPTIONS = (200, 500, 1000, 2000, 5000)
MAX_LOG_LINES = max(LOG_LINE_OPTIONS)
LOG_BACKUP_COUNT = 2


def log_paths(source: str) -> list[Path]:
    """Return allowlisted files in order from oldest to newest."""
    path = LOG_FILES[source]
    return [path.with_name(f"{path.name}.{number}") for number in range(LOG_BACKUP_COUNT, 0, -1)] + [path]


def read_log_tail(source: str, lines: int = DEFAULT_LOG_LINES) -> str:
    """Read a snapshot, reopening each time to tolerate rotation and truncation.

    Only allowlisted sources are accepted. Bound both disk reads and the response,
    even when a single log line is unusually large.
    """
    if not 1 <= lines <= MAX_LOG_LINES:
        raise ValueError("Invalid line count")
    chunks = []
    remaining = MAX_LOG_BYTES
    for path in reversed(log_paths(source)):
        try:
            with path.open("rb") as log_file:
                size = log_file.seek(0, os.SEEK_END)
                start = max(0, size - remaining)
                log_file.seek(start)
                content = log_file.read(min(size, remaining))
        except FileNotFoundError:
            continue
        remaining -= len(content)
        if start:
            # Discard a line (or UTF-8 character) cut off by the byte limit.
            content = content.partition(b"\n")[2]
        chunks.append(content)
        if not remaining:
            break
    if not chunks:
        raise FileNotFoundError("No log files yet")
    content = b"".join(reversed(chunks))
    return "\n".join(content.decode("utf-8", errors="replace").splitlines()[-lines:])


def create_log_download(source: str) -> BinaryIO:
    """Copy all retained entries to a temporary snapshot using bounded memory."""
    paths = log_paths(source)
    snapshot = TemporaryFile(mode="w+b")
    found = False
    try:
        for path in paths:
            try:
                log_file = path.open("rb")
            except FileNotFoundError:
                continue
            found = True
            with log_file:
                remaining = os.fstat(log_file.fileno()).st_size
                while remaining:
                    chunk = log_file.read(min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    snapshot.write(chunk)
                    remaining -= len(chunk)
        if not found:
            raise FileNotFoundError("No log files yet")
        snapshot.seek(0)
        return snapshot
    except BaseException:
        snapshot.close()
        raise
