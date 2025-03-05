from typing import Any

from .course import Course
from .utils import get_course


def get_current_course() -> Course:
    """Get the current course from the Flask app."""
    return get_course()


def get_database_table_data() -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints."""
    course = get_course()

    storage_api = course.storage_api
    all_scores = storage_api.get_all_scores()

    all_tasks = []
    if course.deadlines:
        for group in course.deadlines.get_groups():
            for task in group.tasks:
                if task.enabled:
                    all_tasks.append({"name": task.name, "score": 0, "group": group.name})

    table_data = {"tasks": all_tasks, "students": []}

    for username, student_scores in all_scores.items():
        total_score = sum(student_scores.values())
        table_data["students"].append({"username": username, "scores": student_scores, "total_score": total_score})

    return table_data
