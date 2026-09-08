"""Mark or unmark grade_submissions rows as ignored by GitLab CI job id.

Usage: python -m manytask.scripts.ignore_submission <job_id> [--unignore]
"""

from __future__ import annotations

import argparse
import os
import sys

from manytask.database import DataBaseApi, DatabaseConfig, SubmissionIgnoreChange


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


def ignore_submissions_by_job_id(db_api: DataBaseApi, job_id: int, ignored: bool) -> list[SubmissionIgnoreChange]:
    changes = db_api.set_submissions_ignored_by_job_id(job_id, ignored)

    for course_name in {change.course_name for change in changes}:
        db_api.recalculate_all_scores(course_name)

    return changes


def _print_change(change: SubmissionIgnoreChange) -> None:
    print(
        f"{change.course_name} {change.username} {change.task_name} "
        f"raw_score={change.raw_score} submit_time={change.submit_time} "
        f"ignored: {change.ignored_before} -> {change.ignored_after}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id", type=int, help="GitLab CI job id whose submissions should be (un)ignored")
    parser.add_argument(
        "--unignore", action="store_true", help="Unmark the matching submissions as ignored instead of marking them"
    )
    args = parser.parse_args(argv)

    db_api = build_db_api()
    changes = ignore_submissions_by_job_id(db_api, args.job_id, not args.unignore)

    if not changes:
        print(f"No grade_submissions found with job_id={args.job_id}")
        return 1

    for change in changes:
        _print_change(change)
    return 0


if __name__ == "__main__":
    sys.exit(main())
