from typing import Any

from .main import CustomFlask


def get_database_table_data(app: CustomFlask, course_name: str) -> dict[str, Any]:
    """Get the database table data structure used by both web and API endpoints."""

    storage_api = app.storage_api
    grades_config = storage_api.get_grades(course_name)
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
        total_score = sum(student_scores.values())
        large_count = sum(1 for task in large_tasks if student_scores.get(task[0], 0) >= task[1])
        first_name, last_name = name

        row = {
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "scores": student_scores,
            "total_score": total_score,
            "percent": 0 if max_score == 0 else total_score * 100.0 / max_score,
            "large_count": large_count,
        }

        try:
            row["grade"] = grades_config.evaluate(row)
        except ValueError:
            row["grade"] = 0

        table_data["students"].append(row)
        table_data["max_score"] = max_score

    return table_data
