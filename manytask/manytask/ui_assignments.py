"""Allowlisted assignment data for the React course page."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from manytask.course import ManytaskDeadlinesType
from manytask.utils.generic import SECONDS_PER_DAY, format_remaining


def _task_url(task: Any, group: Any, context: Mapping[str, Any]) -> str:
    if task.url:
        return str(task.url)
    return (
        str(context["task_url_template"])
        .replace("$GROUP_NAME", group.name)
        .replace("$TASK_NAME", task.name)
        .replace("$USER_NAME", str(context["task_url_username"]))
    )


def _deadline_data(deadline: datetime, percent: float, last: datetime, now: datetime) -> dict[str, Any]:
    passed = deadline < now
    remaining_seconds = (deadline - now).total_seconds()
    if passed:
        progress = 100
    elif last > now or deadline <= last:
        progress = 0
    else:
        progress = int(abs((now.timestamp() - last.timestamp()) / (deadline.timestamp() - last.timestamp()) * 100))
    return {
        "at": deadline.isoformat(),
        "percent": percent,
        "passed": passed,
        "urgent": not passed and remaining_seconds < SECONDS_PER_DAY,
        "remaining": "" if passed else "Deadline expires in: " + format_remaining(deadline, now),
        "progress": progress,
        "date": deadline.strftime("%d.%m.%Y"),
        "time": deadline.strftime("%H:%M"),
        "tz": deadline.strftime("%Z"),
    }


def serialize(context: Mapping[str, Any]) -> dict[str, Any]:
    """Use only course data already authorized by ``course_page``."""
    course_name = context["course_name"]
    now = context["now"]
    scores = context["scores"]
    stats = context["task_stats"]
    deadlines_type = context["deadlines_type"]
    groups = []
    for group in context["app"].storage_api.get_groups(course_name, enabled=True, started=True):
        end = group.get_deadline(group.end)
        tasks = []
        for task in group.tasks:
            earned = scores.get(task.name, 0)
            state = (
                "solved"
                if earned == task.score
                else "over_solved"
                if earned > task.score
                else "partial"
                if earned > 0
                else "unsolved"
            )
            tasks.append(
                {
                    "name": task.name,
                    "url": _task_url(task, group, context),
                    "score": task.score,
                    "earned": earned,
                    "bonus": task.is_bonus,
                    "special": task.is_special,
                    "state": state,
                    "statistics": round(float(stats.get(task.name, 0)), 2),
                }
            )
        last = group.start
        deadlines = []
        if deadlines_type != ManytaskDeadlinesType.INTERPOLATE:
            for deadline, percent in group.get_displayed_deadlines(deadlines_type):
                deadlines.append(_deadline_data(deadline, percent, last, now))
                last = deadline
        groups.append(
            {
                "name": group.name,
                "start": group.start.isoformat(),
                "end": end.isoformat(),
                "endDate": end.strftime("%d.%m.%Y"),
                "endTime": end.strftime("%H:%M"),
                "endTz": end.strftime("%Z"),
                "expired": end < now,
                "special": bool(getattr(group, "special", False)),
                "earned": sum(task["earned"] for task in tasks),
                "maximum": sum(task["score"] for task in tasks if not task["bonus"]),
                "tasks": tasks,
                "deadlines": deadlines,
                "graph": group.get_graph_data(now, deadlines_type)
                if deadlines_type == ManytaskDeadlinesType.INTERPOLATE
                else None,
            }
        )
    return {
        "courseName": course_name,
        "now": now.isoformat(),
        "sourcecraftInviteUrl": "https://sourcecraft.dev/me/organizations"
        if context.get("sourcecraft_accept_invite_required")
        else None,
        "groups": groups,
    }
