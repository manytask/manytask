"""Flask bridge for built React pages."""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from flask import render_template, url_for

from .ui_assignments import serialize as serialize_assignments
from .ui_auth import serialize_create_project, serialize_signup, serialize_signup_finish, serialize_signup_yandex_id
from .ui_course_admin import serialize_create as serialize_create_course
from .ui_course_admin import serialize_edit as serialize_edit_course
from .ui_courses import serialize as serialize_courses
from .ui_grades import serialize as serialize_grades
from .ui_shared import serialize_shared

PageSerializer = Callable[[Mapping[str, Any]], dict[str, Any]]
MANIFEST_PATH = Path(__file__).parent / "static" / "dist" / ".vite" / "manifest.json"


def frontend_assets() -> dict[str, Any]:
    """Resolve the Vite entry and CSS for the current hashed build."""
    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
        entry = manifest["src/main.tsx"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Frontend assets are missing or invalid; run 'npm run build' in manytask/frontend"
        ) from error

    css: list[str] = []
    visited: set[str] = set()

    def collect(chunk: Mapping[str, Any]) -> None:
        for file in chunk.get("css", []):
            href = "/static/dist/" + file
            if href not in css:
                css.append(href)
        for name in chunk.get("imports", []):
            if name not in visited:
                visited.add(name)
                collect(manifest[name])

    collect(entry)
    return {"js": "/static/dist/" + entry["file"], "css": css}


def _serialize_not_ready(context: Mapping[str, Any]) -> dict[str, Any]:
    course_name = context["course_name"]
    links = [
        {"label": "Refresh", "href": url_for("course.course_page", course_name=course_name)},
        {"label": "Back to courses list", "href": url_for("root.index")},
    ]
    if context.get("can_edit_course"):
        links.append(
            {"label": "Back to editing course", "href": url_for("instance_admin.edit_course", course_name=course_name)}
        )
    if context.get("is_instance_admin"):
        links.append({"label": "Instance Admin panel", "href": url_for("instance_admin.instance_admin_panel")})
    return {"courseName": course_name, "links": links}


PAGE_SERIALIZERS: dict[str, tuple[str, PageSerializer]] = {
    "not_ready.html": ("not-ready", _serialize_not_ready),
    "signup.html": ("signup", serialize_signup),
    "signup_yandex_id.html": ("signup-yandex-id", serialize_signup_yandex_id),
    "signup_finish.html": ("signup-finish", serialize_signup_finish),
    "create_project.html": ("create-project", serialize_create_project),
    "courses.html": ("courses", serialize_courses),
    "tasks.html": ("assignments", serialize_assignments),
    "database.html": ("grades", serialize_grades),
    "create_course.html": ("create-course", serialize_create_course),
    "edit_course.html": ("edit-course", serialize_edit_course),
}


def render_ui(template_name: str, **context: Any) -> str:
    entry = PAGE_SERIALIZERS.get(template_name)
    if entry is None:
        return render_template(template_name, **context)
    page, serialize = entry
    payload = {
        "schema_version": 1,
        "page": page,
        "shared": serialize_shared(context),
        "data": serialize(context),
    }
    return render_template("ui.html", payload=payload, assets=frontend_assets())
