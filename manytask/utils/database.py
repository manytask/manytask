from typing import Any

from manytask.course import Course
from manytask.main import CustomFlask


def get_database_table_data(app: CustomFlask, course: Course, include_admin_data: bool = False) -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints.

    Set include_admin_data=True to include personal information (first_name, last_name,
    repo URLs, and comments) for admins-only views.
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

    for username, (student_scores, name) in scores_and_names.items():
        total_score = sum(score_solved[0] for score_solved in student_scores.values())

        large_count = sum(1 for large_task in large_tasks if student_scores.get(large_task[0], (0, None))[1])

        first_name, last_name = name

        scores = {name: score[0] for name, score in student_scores.items()}

        row = {
            "username": username,
            "scores": scores,
            "total_score": total_score,
            "percent": 0 if max_score == 0 else total_score * 100.0 / max_score,
            "large_count": large_count,
        }

        if include_admin_data:
            row.update(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "repo_url": app.rms_api.get_url_for_repo(
                        username=username,
                        course_students_group=course.gitlab_course_students_group,
                    ),
                    "comment": storage_api.get_student_comment(course_name, username),
                }
            )

        # Get effective grade (override if exists, otherwise final_grade)
        # If no grade exists yet, calculate and save it
        effective_grade = storage_api.get_effective_grade(course_name, username)

        if effective_grade == 0:
            # No grade saved yet, calculate and save it
            try:
                effective_grade = storage_api.calculate_and_save_grade(course_name, username, row)
            except Exception:
                effective_grade = 0

        row["grade"] = effective_grade

        # Add override indicator (for admins only or for frontend to know)
        # This allows frontend to visually indicate overridden grades
        row["grade_is_override"] = storage_api.is_grade_overridden(course_name, username)

        table_data["students"].append(row)
        table_data["max_score"] = max_score

    return table_data
