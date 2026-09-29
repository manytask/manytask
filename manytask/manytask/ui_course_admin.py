"""Explicit page contracts for the existing course settings routes."""

from collections.abc import Mapping
from typing import Any, cast

from flask import current_app, request, session, url_for

from .course import CourseStatus
from .main import CustomFlask
from .utils.flask import check_if_current_user_is_instance_admin

_CREATE_FIELDS = (
    "unique_course_name", "namespace_id", "registration_secret", "token",
    "course_group", "course_public_repo", "course_students_group", "default_branch",
)
_EDIT_FIELDS = (
    "registration_secret", "gitlab_course_group", "gitlab_course_public_repo",
    "gitlab_course_students_group", "gitlab_default_branch", "course_status",
)


def _rms(context: Mapping[str, Any]) -> str:
    value = context.get("rms", getattr(getattr(current_app, "app_config", None), "rms", "gitlab"))
    return "sourcecraft" if value == "sourcecraft" else "gitlab"


def _labels(context: Mapping[str, Any]) -> dict[str, str]:
    provided = context.get("labels")
    if not isinstance(provided, Mapping):
        provided = getattr(current_app, "create_course_labels", {})
    return {key: value for key, value in provided.items() if isinstance(key, str) and isinstance(value, str)}


def _namespaces() -> tuple[list[dict[str, str | int]], bool, str | None]:
    app = cast(CustomFlask, current_app)
    storage = getattr(app, "storage_api", None)
    username = session.get("manytask", {}).get("username")
    if storage is None or not username:
        return [], False, None
    instance_admin = check_if_current_user_is_instance_admin(app)
    if instance_admin:
        allowed = storage.get_all_namespaces()
    else:
        allowed = [namespace for namespace, role in storage.get_user_namespaces(username) if role == "namespace_admin"]
    namespaces = []
    for namespace in allowed:
        path = getattr(namespace, "gitlab_group_path", None)
        if not isinstance(path, str):
            try:
                path = app.rms_api.get_group_path_by_id(namespace.gitlab_group_id)
            except Exception:
                return [], instance_admin, "Could not load namespace paths. Please refresh the page."
        if not isinstance(path, str):
            return [], instance_admin, "Could not load namespace paths. Please refresh the page."
        namespaces.append({"id": namespace.id, "name": namespace.name, "path": path})
    return namespaces, instance_admin, None


def serialize_create(context: Mapping[str, Any]) -> dict[str, Any]:
    namespaces, instance_admin, path_error = _namespaces()
    values = {name: request.form[name] for name in _CREATE_FIELDS if name in request.form}
    if "token" not in values:
        token = context.get("generated_token")
        values["token"] = token if isinstance(token, str) else ""
    if "default_branch" not in values:
        values["default_branch"] = "main"
    selected = request.args.get("namespace_id")
    allowed_ids = {str(namespace["id"]) for namespace in namespaces}
    locked = False
    namespace_error = path_error
    if selected is not None and request.method == "GET" and path_error is None:
        if selected in allowed_ids or selected == "0" and instance_admin:
            values["namespace_id"] = selected
            locked = True
        else:
            namespace_error = f"Namespace with ID {selected} not found or you don't have access."
    if "namespace_id" not in values:
        values["namespace_id"] = str(namespaces[0]["id"]) if namespaces else "0"
    return {
        "action": url_for("instance_admin.create_course"), "mode": "create", "rms": _rms(context),
        "labels": _labels(context), "values": values, "namespaces": namespaces,
        "statuses": [], "showAllScores": request.form.get(
            "show_allscores", "off" if request.method == "POST" else "on"
        ) == "on",
        "accessUrls": None, "courseUsers": [], "namespaceLocked": locked,
        "namespaceError": namespace_error, "allowNoNamespace": instance_admin,
    }


def serialize_edit(context: Mapping[str, Any]) -> dict[str, Any]:
    course = context.get("course")
    name = getattr(course, "course_name", None)
    if not isinstance(name, str):
        name = request.view_args.get("course_name") if request.view_args else None
    if not isinstance(name, str):
        name = ""
    values = {field: str(value) for field in _EDIT_FIELDS if (value := getattr(course, field, None)) is not None}
    status = getattr(course, "status", None)
    if status is not None:
        values["course_status"] = str(getattr(status, "value", status))
    values["course_name"] = name
    token = getattr(course, "token", None)
    if isinstance(token, str):
        values["token"] = token
    # Restore the user's text on failed POST while never accepting a posted token.
    values.update({field: request.form[field] for field in _EDIT_FIELDS if field in request.form})
    users = []
    for row in context.get("course_users") or []:
        if not isinstance(row, tuple):
            continue
        try:
            user, _is_admin = row
        except ValueError:
            continue
        username = getattr(user, "username", None)
        if isinstance(username, str):
            users.append({
                "username": username,
                "firstName": str(getattr(user, "first_name", "") or ""),
                "lastName": str(getattr(user, "last_name", "") or ""),
            })
    return {
        "action": url_for("instance_admin.edit_course", course_name=name),
        "mode": "edit", "rms": _rms(context), "labels": _labels(context),
        "values": values, "namespaces": [],
        "statuses": [
            {"value": status.value, "label": status.value.replace("_", " ").title()}
            for status in CourseStatus
        ],
        "showAllScores": request.form.get("show_allscores") == "on" if request.method == "POST"
        else bool(getattr(course, "show_allscores", True)),
        "accessUrls": {
            "users": url_for("api.get_course_access_users", course_name=name),
            "courseAdmin": url_for("api.set_course_admin", course_name=name),
        } if course is not None else None,
        "courseUsers": users,
        "cancelUrl": url_for("course.course_page", course_name=name) if course is not None else None,
    }
