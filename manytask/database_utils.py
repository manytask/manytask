from typing import Any

from .main import CustomFlask


def get_database_table_data(app: CustomFlask, course_name: str) -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints."""

    storage_api = app.storage_api
    all_scores = storage_api.get_all_scores(course_name)

    all_tasks = []
    for group in storage_api.get_groups(course_name):
        for task in group.tasks:
            if task.enabled:
                all_tasks.append({"name": task.name, "score": 0, "group": group.name})

    table_data = {"tasks": all_tasks, "students": []}

    for username, student_scores in all_scores.items():
        total_score = sum(student_scores.values())
        student_name = app.gitlab_api.get_student_by_username(username).name
        table_data["students"].append(
            {"username": username, "student_name": student_name, "scores": student_scores, "total_score": total_score}
        )

    return table_data
