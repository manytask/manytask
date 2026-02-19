from typing import Any

from manytask.course import Course
from manytask.database import calculate_effective_grade
from manytask.main import CustomFlask


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
    grades_config = storage_api.get_grades(course_name)

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

    for username, (
        student_scores_with_solved,
        name,
        final_grade,
        final_grade_override,
        comment,
    ) in scores_and_names.items():
        # student_scores_with_solved = {task_name: (score, is_solved)}
        student_scores = {task_name: score for task_name, (score, _) in student_scores_with_solved.items()}
        total_score = sum(student_scores.values())
        large_count = sum(1 for task in large_tasks if student_scores.get(task[0], 0) >= task[1])

        first_name, last_name = name

        row: dict[str, Any] = {
            "username": username,
            "scores": student_scores,
            "total_score": total_score,
            "percent": 0 if max_score == 0 else total_score * 100.0 / max_score,
            "large_count": large_count,
        }

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
                    "comment": comment,
                }
            )

        if final_grade_override is not None:
            effective_grade = final_grade_override
            grade_is_override = True
        else:
            effective_grade = calculate_effective_grade(
                course.status,
                grades_config,
                row,
                final_grade,
            )
            grade_is_override = False

        row["grade"] = effective_grade
        row["grade_is_override"] = grade_is_override

        table_data["students"].append(row)
        table_data["max_score"] = max_score

    return table_data
