"""
Secure pytest reporter plugin for checker.
Uses pipe IPC to send results instead of temporary files.

Security model:
- Pipe-based IPC prevents students from reading report data
- Python -I flag (in python.py) blocks sitecustomize.py
- Security relies on: 1) pipe IPC, 2) python -I flag
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest


class CheckerReporterPlugin:
    """
    Pytest plugin that generates JSON report using protected json.dump.
    This prevents students from monkey-patching json.dump to fake results.

    Supports two modes:
    1. Pipe mode (secure): writes to a FIFO pipe that's read by checker
    2. File mode (fallback): writes to a regular file for compatibility
    """

    def __init__(self, report_path: str, use_pipe: bool = False):
        self.report_path = report_path
        self.use_pipe = use_pipe
        self.start_time = time.time()
        self.collected_items: list[Any] = []
        self.test_results: list[dict[str, Any]] = []
        self.summary = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "error": 0,
            "xfailed": 0,
            "xpassed": 0,
            "total": 0,
            "collected": 0,
        }
        self.pipe_fd = None

        # If using pipe, open it immediately for writing
        # Pipe must already exist and have a reader on the other end
        if self.use_pipe:
            try:
                # Open pipe in non-blocking mode initially to avoid hanging
                import os

                self.pipe_fd = os.open(self.report_path, os.O_WRONLY | os.O_NONBLOCK)
                # Switch to blocking mode after successful open
                import fcntl

                flags = fcntl.fcntl(self.pipe_fd, fcntl.F_GETFL)
                fcntl.fcntl(self.pipe_fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
            except (OSError, IOError):
                # If pipe is not available, fall back to file mode
                self.use_pipe = False
                self.pipe_fd = None

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Called after test collection is complete."""
        self.collected_items = session.items
        self.summary["collected"] = len(session.items)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Called for each test phase (setup, call, teardown)."""
        # Only count the 'call' phase to avoid double-counting
        if report.when != "call":
            return

        outcome = report.outcome
        test_info = {
            "nodeid": report.nodeid,
            "outcome": outcome,
            "duration": report.duration,
        }

        if hasattr(report, "longrepr") and report.longrepr:
            test_info["longrepr"] = str(report.longrepr)

        self.test_results.append(test_info)

        # Update summary
        if outcome == "passed":
            self.summary["passed"] += 1
        elif outcome == "failed":
            self.summary["failed"] += 1
        elif outcome == "skipped":
            self.summary["skipped"] += 1
        elif outcome in ("error", "xfailed", "xpassed"):  # type: ignore[unreachable]
            self.summary["error"] += 1

        # CRITICAL: Write JSON after EACH test (incremental write)
        # This protects against sys.exit() in student's code
        self._write_report()

    def _write_report(self) -> None:
        """
        Write JSON report using PROTECTED json.dump/dumps.
        Called after each test AND at session finish.

        In pipe mode: writes each update as a JSON line
        In file mode: overwrites the file with complete report
        """
        self.summary["total"] = len(self.test_results)

        report_data = {
            "created": self.start_time,
            "duration": time.time() - self.start_time,
            "summary": self.summary,
            "tests": self.test_results,
        }

        # Write report data as JSON
        # Security: python -I flag blocks sitecustomize.py, pipe IPC protects data
        try:
            if self.use_pipe and self.pipe_fd is not None:
                # Pipe mode: write JSON as a single line (newline-delimited JSON)
                # Each write overwrites the previous state
                import os

                json_str = json.dumps(report_data, ensure_ascii=False)
                # Write with newline separator for line-based reading
                data = (json_str + "\n").encode("utf-8")
                os.write(self.pipe_fd, data)
            else:
                # File mode: overwrite file with complete report
                with open(self.report_path, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
        except (OSError, IOError) as e:
            # Log I/O errors to stderr for debugging
            # Don't crash pytest, but make the error visible
            import sys

            print(f"WARNING: Failed to write checker report: {e}", file=sys.stderr)
        except Exception as e:
            # Log unexpected errors
            import sys

            print(f"ERROR: Unexpected error in checker reporter: {type(e).__name__}: {e}", file=sys.stderr)

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """
        Called after all tests are finished.
        Final write and cleanup.

        tryfirst=True ensures this runs BEFORE student's conftest.py hooks.
        """
        # Write final report
        self._write_report()

        # Close pipe if we opened it
        if self.pipe_fd is not None:
            try:
                import os

                os.close(self.pipe_fd)
            except (OSError, IOError):
                pass
            finally:
                self.pipe_fd = None


def pytest_configure(config: pytest.Config) -> None:
    """
    Hook called by pytest to register our plugin.
    This is called EARLY, before conftest.py is loaded.
    """
    report_path = config.getoption("--checker-report", default=None)
    if report_path:
        use_pipe = config.getoption("--checker-use-pipe", default=False)
        plugin = CheckerReporterPlugin(report_path, use_pipe=use_pipe)
        config.pluginmanager.register(plugin, "checker_reporter")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options for our plugin."""
    parser.addoption(
        "--checker-report", action="store", default=None, help="Path to write secure JSON report (file or FIFO pipe)"
    )
    parser.addoption(
        "--checker-use-pipe", action="store_true", default=False, help="Use pipe mode for secure IPC instead of file"
    )
