"""Mark a large task as solved (grades.is_solved) for everyone who reached a score threshold.

Use it to credit a large task retroactively, e.g. when min_score was misconfigured. Once marked,
the task stays solved even if min_score is raised later (see count_solved_large_tasks).

Dry run by default: prints what would change and touches nothing.

Usage (inside the manytask container, DATABASE_URL must be set):

    python -m manytask.scripts.mark_large_task_solved python_2026_fall \\
        --group 04.3.HW1 --task vm --min-score 320 [--report changes.csv]

    # actually write to the DB
    ... --apply

    # course is already in DORESHKA / FINISHED: grades are frozen (or capped at 3) there,
    # --unfreeze recalculates them as in ALL_TASKS_ISSUED: max(saved, calculated), no downgrades
    ... --apply --unfreeze

What it does (in a single transaction):
  * grades.is_solved := true where score >= --min-score (default: the task's current min_score);
  * users_on_courses.final_grade := recalculated grade, exactly like recalculate_all_grades()
    does after a config push (students with final_grade_override are skipped).
Nothing is ever un-marked.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import sys
from dataclasses import dataclass
from typing import Any

from manytask import models
from manytask.abstract import StudentCourseScores, TaskScore
from manytask.course import CourseStatus
from manytask.database import DataBaseApi, DatabaseConfig, calculate_effective_grade
from manytask.models import User, UserOnCourse
from manytask.utils.generic import calculate_percent

FROZEN_STATUSES = {CourseStatus.DORESHKA, CourseStatus.FINISHED}


@dataclass
class StudentChange:
    username: str
    task_score: int | None
    newly_solved: bool
    old_large_count: int
    new_large_count: int
    saved_grade: int | None
    old_grade: int
    new_grade: int
    is_override: bool

    @property
    def grade_changed(self) -> bool:
        return not self.is_override and self.new_grade != self.old_grade

    @property
    def needs_grade_write(self) -> bool:
        return not self.is_override and self.new_grade != self.saved_grade


def build_db_api() -> DataBaseApi:
    database_url = os.environ.get("DATABASE_URL")
    if database_url is None:
        raise EnvironmentError("Unable to find DATABASE_URL env")

    instance_admin_username = os.environ.get("INITIAL_INSTANCE_ADMIN", "admin")
    return DataBaseApi(DatabaseConfig(database_url=database_url, instance_admin_username=instance_admin_username))


def _find_task(session: Any, course_name: str, group_name: str | None, task_name: str) -> models.Task:
    course = session.query(models.Course).filter_by(name=course_name).one_or_none()
    if course is None:
        raise SystemExit(f"Course '{course_name}' not found")

    query = (
        session.query(models.Task)
        .join(models.TaskGroup)
        .filter(models.TaskGroup.course_id == course.id, models.Task.name == task_name)
    )
    if group_name is not None:
        query = query.filter(models.TaskGroup.name == group_name)
    tasks = query.all()
    if len(tasks) != 1:
        where = f"group '{group_name}' of " if group_name else ""
        raise SystemExit(f"Expected exactly one task '{task_name}' in {where}'{course_name}', found {len(tasks)}")
    return tasks[0]


def compute_changes(
    db: DataBaseApi,
    course_name: str,
    task_name: str,
    threshold: int,
    calc_status: CourseStatus,
) -> list[StudentChange]:
    """Same math as recalculate_all_grades(), before and after marking."""
    course = db.get_course(course_name)
    assert course is not None
    grades_config = db.get_grades(course_name)
    students = db.get_all_scores_with_names(course_name)

    large_tasks: list[tuple[str, int]] = []
    max_score = 0
    for group in db.get_groups(course_name, enabled=True, started=True):
        for task in group.tasks:
            if not task.enabled:
                continue
            if not task.is_bonus:
                max_score += task.score
            if task.is_large:
                large_tasks.append((task.name, task.min_score))

    changes = []
    for username, student in students.items():
        current = student.task_scores.get(task_name)
        newly_solved = current is not None and not current.is_solved and current.score >= threshold

        after = student
        if newly_solved:
            assert current is not None
            after = dataclasses.replace(
                student, task_scores={**student.task_scores, task_name: TaskScore(current.score, True)}
            )

        total = student.total_score
        base: dict[str, Any] = {"total_score": total, "percent": calculate_percent(total, max_score)}
        old_lc = student.count_solved_large_tasks(large_tasks)
        new_lc = after.count_solved_large_tasks(large_tasks)

        old_grade, new_grade = _grades(student, course.status, calc_status, grades_config, base, old_lc, new_lc)
        changes.append(
            StudentChange(
                username=username,
                task_score=None if current is None else current.score,
                newly_solved=newly_solved,
                old_large_count=old_lc,
                new_large_count=new_lc,
                saved_grade=student.final_grade,
                old_grade=old_grade,
                new_grade=new_grade,
                is_override=student.final_grade_override is not None,
            )
        )
    return changes


def _grades(
    student: StudentCourseScores,
    status: CourseStatus,
    calc_status: CourseStatus,
    grades_config: Any,
    base: dict[str, Any],
    old_lc: int,
    new_lc: int,
) -> tuple[int, int]:
    if student.final_grade_override is not None:
        return student.final_grade_override, student.final_grade_override
    # old: what the scores table shows right now
    old = calculate_effective_grade(status, grades_config, {**base, "large_count": old_lc}, student.final_grade)
    new = calculate_effective_grade(calc_status, grades_config, {**base, "large_count": new_lc}, student.final_grade)
    return old, new


def apply_changes(
    db: DataBaseApi,
    course_name: str,
    group_name: str | None,
    task_name: str,
    changes: list[StudentChange],
) -> tuple[int, int]:
    to_mark = {c.username for c in changes if c.newly_solved}
    to_grade = {c.username: c.new_grade for c in changes if c.needs_grade_write}

    with db._session_create() as session:
        task = _find_task(session, course_name, group_name, task_name)
        uocs = (
            session.query(UserOnCourse)
            .join(User, User.id == UserOnCourse.user_id)
            .filter(UserOnCourse.course_id == task.group.course_id, User.username.in_(to_mark | set(to_grade)))
            .all()
        )
        uoc_by_username = {uoc.user.username: uoc for uoc in uocs}

        marked = 0
        for username in to_mark:
            grade = (
                session.query(models.Grade)
                .filter_by(user_on_course_id=uoc_by_username[username].id, task_id=task.id)
                .with_for_update()
                .one()
            )
            if not grade.is_solved:
                grade.is_solved = True
                marked += 1

        for username, new_grade in to_grade.items():
            uoc = uoc_by_username[username]
            if uoc.final_grade_override is None:  # never touch overridden grades
                uoc.final_grade = new_grade

        session.commit()
    return marked, len(to_grade)


def print_summary(changes: list[StudentChange]) -> list[StudentChange]:
    """Print what changes; return the list of downgrades."""
    marked = [c for c in changes if c.newly_solved]
    lc_changed = [c for c in changes if c.new_large_count != c.old_large_count]
    gr_changed = [c for c in changes if c.grade_changed]
    downgrades = [c for c in gr_changed if c.new_grade < c.old_grade]
    overridden = [c for c in marked if c.is_override]

    print(f"students: {len(changes)}")
    print(f"to mark is_solved: {len(marked)}")
    print(f"large_count changes: {len(lc_changed)}")
    print(f"grade changes: {len(gr_changed)}")
    transitions: dict[tuple[int, int], int] = {}
    for c in gr_changed:
        transitions[(c.old_grade, c.new_grade)] = transitions.get((c.old_grade, c.new_grade), 0) + 1
    for (old, new), n in sorted(transitions.items()):
        print(f"  {old} -> {new}: {n}")
    if overridden:
        print(
            f"NOTE: {len(overridden)} of them have a manual grade override, the override is kept: "
            + ", ".join(c.username for c in overridden)
        )
    if downgrades:
        print(
            f"WARNING: {len(downgrades)} downgrades: "
            + ", ".join(f"{c.username} {c.old_grade}->{c.new_grade}" for c in downgrades)
        )
    return downgrades


def write_report(path: str, changes: list[StudentChange]) -> None:
    fields = [f.name for f in dataclasses.fields(StudentChange)]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for c in sorted(changes, key=lambda c: c.username.lower()):
            writer.writerow(["" if getattr(c, name) is None else getattr(c, name) for name in fields])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course_name")
    parser.add_argument("--task", required=True, help="large task name, e.g. vm")
    parser.add_argument("--group", help="task group name, e.g. 04.3.HW1 (optional, for safety)")
    parser.add_argument("--min-score", type=int, help="threshold to mark as solved (default: task's min_score)")
    parser.add_argument("--apply", action="store_true", help="write to the DB (default: dry run)")
    parser.add_argument(
        "--unfreeze",
        action="store_true",
        help="for DORESHKA/FINISHED courses: recalc as ALL_TASKS_ISSUED (max(saved, calculated), no cap)",
    )
    parser.add_argument("--allow-downgrade", action="store_true", help="allow writes that lower someone's grade")
    parser.add_argument("--report", help="write a per-student CSV report to this path")
    args = parser.parse_args(argv)

    db = build_db_api()

    with db._session_create() as session:
        task = _find_task(session, args.course_name, args.group, args.task)
        is_large, current_min_score = task.is_large, task.min_score
        group_name, status = task.group.name, task.group.course.status

    threshold = current_min_score if args.min_score is None else args.min_score
    print(f"course={args.course_name} status={status.value}")
    print(f"task={group_name}/{args.task} is_large={is_large} min_score={current_min_score} threshold={threshold}")
    if not is_large:
        print("ERROR: task is not marked is_large, is_solved has no effect for it", file=sys.stderr)
        return 1
    if threshold <= 0:
        print("ERROR: threshold must be positive", file=sys.stderr)
        return 1

    calc_status = status
    if status in FROZEN_STATUSES:
        if args.unfreeze:
            calc_status = CourseStatus.ALL_TASKS_ISSUED
            print(f"--unfreeze: recalculating grades as {calc_status.value} (no downgrades, no doreshka cap)")
        else:
            print(
                f"WARNING: course is {status.value}: grades are frozen"
                + (" / capped at 3" if status == CourseStatus.DORESHKA else "")
                + ", so they will barely change. Use --unfreeze to recalculate them properly."
            )

    changes = compute_changes(db, args.course_name, args.task, threshold, calc_status)
    downgrades = print_summary(changes)

    if args.report:
        write_report(args.report, changes)
        print(f"report written to {args.report}")

    if not args.apply:
        print("\nDry run, nothing written. Re-run with --apply.")
        return 0

    if downgrades and not args.allow_downgrade:
        print("Refusing to apply because of downgrades (use --allow-downgrade if this is intended).", file=sys.stderr)
        return 1

    marked, graded = apply_changes(db, args.course_name, args.group, args.task, changes)
    print(f"\nDONE: is_solved set for {marked} students, final_grade written for {graded} students.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
