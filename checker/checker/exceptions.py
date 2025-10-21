from __future__ import annotations

from dataclasses import dataclass


class CheckerException(Exception):
    """Base exception for Checker package"""

    __test__ = False  # to disable pytest detecting it as Test class
    pass


class CheckerValidationError(CheckerException):
    """Base validation error of configs, project structure, etc."""

    pass


class BadConfig(CheckerValidationError):
    """All configs exceptions: deadlines, checker and tasks configs"""

    pass


class BadStructure(CheckerValidationError):
    """Course structure exception: some files are missing, etc."""

    pass


class ExportError(CheckerException):
    """Export stage exception"""

    pass


class TestingError(CheckerException):
    """All testers exceptions can occur during testing stage"""

    pass


@dataclass
class PluginExecutionFailed(TestingError):
    """Exception raised when plugin execution failed"""

    message: str = ""
    output: str | None = None
    percentage: float = 0.0
