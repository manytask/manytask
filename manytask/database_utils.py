from typing import Any

from flask import current_app

from .course import Course


def get_database_table_data() -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints."""
    course: Course = current_app.course  # type: ignore

    storage_api = course.storage_api
    all_scores = storage_api.get_all_scores()

    all_tasks = []
    if course.deadlines:
        for group in course.deadlines.get_groups():
            for task in group.tasks:
                if task.enabled and group.enabled:
                    all_tasks.append({"name": task.name, "score": 0, "group": group.name})

    table_data = {"tasks": all_tasks, "students": []}

    for username, student_scores in all_scores.items():
        total_score = sum(student_scores.values())
        student_name = course.gitlab_api.get_student_by_username(username).name
        table_data["students"].append(
            {"username": username, "student_name": student_name, "scores": student_scores, "total_score": total_score}
        )

    return table_data
