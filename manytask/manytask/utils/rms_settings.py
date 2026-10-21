from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from manytask.abstract import RmsApi, StorageApi

logger = logging.getLogger(__name__)

_courses_in_progress: set[str] = set()
_courses_in_progress_lock = threading.Lock()


@dataclass
class ProjectReconcileResult:
    project_path: str
    changed: bool
    error: str | None = None


@dataclass
class ReconcileResult:
    course_name: str
    projects: list[ProjectReconcileResult] = field(default_factory=list)

    @property
    def checked(self) -> int:
        return len(self.projects)

    @property
    def changed(self) -> int:
        return sum(1 for project in self.projects if project.changed and project.error is None)

    @property
    def failed(self) -> int:
        return sum(1 for project in self.projects if project.error is not None)

    @property
    def success(self) -> bool:
        return self.failed == 0


def reconcile_course_rms_settings(storage_api: StorageApi, rms_api: RmsApi, course_name: str) -> ReconcileResult:
    """Apply the course's rms settings to every student project. Synchronous; safe to call repeatedly.

    Clears the course's rms_settings_pending flag if (and only if) every project succeeded.
    """
    course = storage_api.get_course(course_name)
    if course is None:
        raise ValueError(f"Course {course_name} not found")

    result = ReconcileResult(course_name=course_name)
    for project_path in rms_api.list_group_projects(course.gitlab_course_students_group):
        try:
            changed = rms_api.ensure_project_settings(project_path, course.ci_config_path, course.protected_branches)
            result.projects.append(ProjectReconcileResult(project_path=project_path, changed=changed))
        except Exception as e:
            logger.exception("Failed to apply RMS settings to project=%s course=%s", project_path, course_name)
            result.projects.append(ProjectReconcileResult(project_path=project_path, changed=False, error=str(e)))

    logger.info(
        "RMS settings reconcile for course=%s: checked=%s changed=%s failed=%s",
        course_name,
        result.checked,
        result.changed,
        result.failed,
    )

    if result.success:
        storage_api.clear_rms_settings_pending(course_name)

    return result


def schedule_rms_settings_reconcile(storage_api: StorageApi, rms_api: RmsApi, course_name: str) -> bool:
    """Start a background reconcile pass for course_name unless one is already running.

    :returns: whether a new pass was started
    """
    with _courses_in_progress_lock:
        if course_name in _courses_in_progress:
            logger.info("RMS settings reconcile already running for course=%s, skipping", course_name)
            return False
        _courses_in_progress.add(course_name)

    def _run() -> None:
        try:
            reconcile_course_rms_settings(storage_api, rms_api, course_name)
        finally:
            with _courses_in_progress_lock:
                _courses_in_progress.discard(course_name)

    threading.Thread(target=_run, daemon=True, name=f"rms-reconcile-{course_name}").start()
    return True
