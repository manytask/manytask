"""Explicit shared data for the React page envelope."""

from collections.abc import Mapping
from typing import Any, cast

from flask import current_app, get_flashed_messages, session, url_for
from flask_wtf.csrf import generate_csrf


def _course_data(context: Mapping[str, Any]) -> dict[str, Any] | None:
    name = context.get("course_name")
    if not isinstance(name, str):
        return None

    status = context.get("course_status", "")
    if hasattr(status, "value"):
        status = status.value
    scores = context.get("scores")
    score = (
        sum(value for value in scores.values() if isinstance(value, (int, float))) if isinstance(scores, Mapping) else 0
    )
    bonus_score = context.get("bonus_score", 0)
    max_started_score = context.get("max_started_score", 0)
    return {
        "name": name,
        "status": str(status),
        "score": score,
        "bonusScore": bonus_score if isinstance(bonus_score, (int, float)) else 0,
        "maxStartedScore": max_started_score if isinstance(max_started_score, (int, float)) else 0,
    }


def serialize_shared(context: Mapping[str, Any]) -> dict[str, Any]:
    """Select only the fields needed by the common UI; never serialize session or app."""
    user_session = session.get("manytask", {})
    username = context.get("username") or user_session.get("username") or ("guest" if current_app.debug else None)
    course = _course_data(context)
    can_edit_course = bool(context.get("can_edit_course") or context.get("is_course_admin"))
    instance_admin = bool(context.get("is_instance_admin"))
    can_create_courses = bool(context.get("can_create_courses"))

    navigation = [{"label": "Courses", "href": url_for("root.index")}]
    if course is not None:
        navigation.append({"label": "Assignments", "href": url_for("course.course_page", course_name=course["name"])})
        for label, key in (("My Repo", "student_repo_url"), ("My Submits", "student_ci_url")):
            href = context.get(key)
            if isinstance(href, str):
                navigation.append({"label": label, "href": href})
        if context.get("show_allscores"):
            navigation.append(
                {"label": "All Scores", "href": url_for("course.show_database", course_name=course["name"])}
            )
        if can_edit_course:
            navigation.append(
                {"label": "Edit Course", "href": url_for("instance_admin.edit_course", course_name=course["name"])}
            )
    if instance_admin:
        navigation.append({"label": "Instance Admin panel", "href": url_for("instance_admin.instance_admin_panel")})
    links = context.get("links")
    if isinstance(links, Mapping):
        navigation.extend(
            {"label": label, "href": href}
            for label, href in links.items()
            if isinstance(label, str) and isinstance(href, str)
        )

    courses = [
        {"label": item["name"], "href": item["url"]}
        for item in context.get("courses", []) or []
        if isinstance(item, Mapping) and isinstance(item.get("name"), str) and isinstance(item.get("url"), str)
    ]
    app_config = getattr(current_app, "app_config", None)
    rms = "sourcecraft" if getattr(app_config, "rms", "gitlab") == "sourcecraft" else "gitlab"
    favicon = context.get("course_favicon") or getattr(current_app, "favicon", "favicon.ico")
    flashes = cast(list[tuple[str, str]], get_flashed_messages(with_categories=True))

    return {
        "csrfToken": generate_csrf(),
        "username": username,
        "firstName": str(context.get("first_name") or ""),
        "lastName": str(context.get("last_name") or ""),
        "version": str(context.get("manytask_version") or getattr(current_app, "manytask_version", "") or ""),
        "favicon": url_for("static", filename=favicon),
        "rms": rms,
        "errorMessage": context.get("error_message"),
        "flashes": [{"category": category, "message": message} for category, message in flashes],
        "navigation": navigation,
        "courses": courses,
        "urls": {
            "home": url_for("root.index"),
            "login": url_for("root.login"),
            "logout": url_for("root.logout"),
            "updateProfile": url_for("root.update_profile"),
        },
        "capabilities": {
            "instanceAdmin": instance_admin,
            "namespaceAdmin": bool(context.get("is_namespace_admin")),
            "courseAdmin": bool(context.get("is_course_admin")),
            "canCreateCourses": can_create_courses,
            "canEditCourse": can_edit_course,
        },
        "course": course,
    }
