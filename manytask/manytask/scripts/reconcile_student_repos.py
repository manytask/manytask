"""Apply a course's rms settings (ci_config_path, protected_branches) to every student repository.

Usage: python -m manytask.scripts.reconcile_student_repos <course_name>
"""

from __future__ import annotations

import argparse
import os
import sys

from manytask.database import DataBaseApi, DatabaseConfig
from manytask.glab import GitLabApi, GitLabConfig
from manytask.utils.rms_settings import ReconcileResult, reconcile_course_rms_settings


def build_db_api() -> DataBaseApi:
    database_url = os.environ.get("DATABASE_URL")
    if database_url is None:
        raise EnvironmentError("Unable to find DATABASE_URL env")

    instance_admin_username = os.environ.get("INITIAL_INSTANCE_ADMIN", "admin")
    return DataBaseApi(
        DatabaseConfig(
            database_url=database_url,
            instance_admin_username=instance_admin_username,
        )
    )


def build_gitlab_api() -> GitLabApi:
    gitlab_url = os.environ.get("GITLAB_URL")
    if gitlab_url is None:
        raise EnvironmentError("Unable to find GITLAB_URL env")

    admin_token = os.environ.get("GITLAB_ADMIN_TOKEN")
    if admin_token is None:
        raise EnvironmentError("Unable to find GITLAB_ADMIN_TOKEN env")

    verify_ssl = os.environ.get("GITLAB_VERIFY_SSL", "true").lower() in ("true", "1", "yes")
    return GitLabApi(GitLabConfig(base_url=gitlab_url, admin_token=admin_token, verify_ssl=verify_ssl))


def _print_result(result: ReconcileResult) -> None:
    for project in result.projects:
        if project.error is not None:
            print(f"{project.project_path}: FAILED ({project.error})")
        elif project.changed:
            print(f"{project.project_path}: changed")
        else:
            print(f"{project.project_path}: already up to date")

    print(
        f"course={result.course_name} checked={result.checked} changed={result.changed} failed={result.failed}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("course_name", help="Course name to reconcile RMS settings for")
    args = parser.parse_args(argv)

    db_api = build_db_api()
    rms_api = build_gitlab_api()

    result = reconcile_course_rms_settings(db_api, rms_api, args.course_name)
    _print_result(result)

    return 1 if not result.success else 0


if __name__ == "__main__":
    sys.exit(main())
