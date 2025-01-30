from typing import Any

from flask import current_app

from .course import Course


def get_database_table_data() -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints."""
    course: Course = current_app.course  # type: ignore

    storage_api = course.storage_api
    all_scores = storage_api.get_all_scores()

    all_task_names = []
    if course.deadlines:
        for group in course.deadlines.get_groups():
            for task in group.tasks:
                if task.enabled:
                    all_task_names.append(task.name)

    table_data = {"tasks": [{"name": task_name, "score": 0} for task_name in all_task_names], "students": []}

    for username, student_scores in all_scores.items():
        total_score = sum(student_scores.values())
        table_data["students"].append({"username": username, "scores": student_scores, "total_score": total_score})

    return table_data
