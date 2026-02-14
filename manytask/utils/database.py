from typing import Any

from manytask.course import Course
from manytask.main import CustomFlask


def build_grade_row(
    username: str,
    student_scores: dict[str, int],
    max_score: int,
    large_tasks: list[tuple[str, int]],
    total_score: int | None = None,
) -> dict[str, Any]:
    """Build a grade calculation row used by grade evaluation logic."""

    if total_score is None:
        total_score = sum(student_scores.values())

    large_count = sum(1 for task_name, min_score in large_tasks if student_scores.get(task_name, 0) >= min_score)

    return {
        "username": username,
        "scores": student_scores,
        "total_score": total_score,
        "percent": 0 if max_score == 0 else total_score * 100.0 / max_score,
        "large_count": large_count,
    }


def get_database_table_data(
    app: CustomFlask,
    course: Course,
    include_admin_data: bool = False,
    is_program_manager: bool = False,
) -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints.

    Set include_admin_data=True to include per-student repo URLs, comments, and full names (for admins-only views).
    Set is_program_manager=True to include student full names (for program managers).
    """

    course_name = course.course_name
    storage_api = app.storage_api
    scores_and_names = storage_api.get_all_scores_with_names(course_name)

    all_tasks = []
    large_tasks = []
    max_score: int = 0
    for group in storage_api.get_groups(course_name, enabled=True, started=True):
        for task in group.tasks:
            if task.enabled:
                all_tasks.append({"name": task.name, "score": 0, "group": group.name})
                if not task.is_bonus:
                    max_score += task.score
                if task.is_large:
                    large_tasks.append((task.name, task.min_score))

    table_data: dict[str, Any] = {"tasks": all_tasks, "students": []}

    for username, (student_scores_with_solved, name, final_grade, final_grade_override) in scores_and_names.items():
        # student_scores_with_solved = {task_name: (score, is_solved)}
        student_scores = {task_name: score for task_name, (score, _) in student_scores_with_solved.items()}

        first_name, last_name = name

        row = build_grade_row(
            username=username,
            student_scores=student_scores,
            max_score=max_score,
            large_tasks=large_tasks,
        )

        if include_admin_data or is_program_manager:
            row["first_name"] = first_name
            row["last_name"] = last_name

        if include_admin_data:
            row.update(
                {
                    "repo_url": app.rms_api.get_url_for_repo(
                        username=username,
                        course_students_group=course.gitlab_course_students_group,
                    ),
                    "comment": storage_api.get_student_comment(course_name, username),
                }
            )

        # Determine effective grade:
        # - If override exists, use it
        # - Otherwise, recalculate and save (allows downgrade in IN_PROGRESS, but not in DORESHKA/ALL_TASKS_ISSUED)
        if final_grade_override is not None:
            effective_grade = final_grade_override
        elif final_grade is not None:
            effective_grade = final_grade
        else:
            effective_grade = storage_api.calculate_and_save_grade(course_name, username, row)

        row["grade"] = effective_grade

        # Add override indicator using already loaded data
        row["grade_is_override"] = final_grade_override is not None

        table_data["students"].append(row)
        table_data["max_score"] = max_score

    return table_data
