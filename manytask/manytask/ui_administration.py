"""Allowlisted presentation data from authorized administration route contexts."""

from collections.abc import Mapping
from typing import Any

from flask import url_for

ROLES = [
    {"value": "namespace_admin", "label": "Namespace Admin"},
    {"value": "program_manager", "label": "Program Manager"},
    {"value": "student", "label": "Demote to Student"},
]


def _namespace(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["name"],
        "slug": item["slug"],
        "description": item.get("description") or "",
        "gitlabGroupId": item.get("gitlab_group_id"),
        "usersCount": item.get("users_count", 0),
        "coursesCount": item.get("courses_count", 0),
        "href": url_for("instance_admin.namespace_panel", namespace_id=item["id"]),
    }


def serialize_namespaces(context: Mapping[str, Any]) -> dict[str, Any]:
    return {"namespaces": [_namespace(item) for item in context.get("namespaces", [])]}


def serialize_instance(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action": url_for("instance_admin.instance_admin_panel"),
        "users": [
            {
                "id": user.user_id,
                "username": user.username,
                "firstName": user.first_name or "",
                "lastName": user.last_name or "",
                "instanceAdmin": bool(user.instance_admin),
            }
            for user in context.get("users", [])
        ],
        **serialize_namespaces(context),
        "namespaceApiUrl": url_for("namespace_api.create_namespace"),
        "namespacePanelUrlTemplate": url_for("instance_admin.namespace_panel", namespace_id=0),
        "createCourseUrl": url_for("instance_admin.create_course"),
        "courses": [
            {
                "name": course["name"],
                "href": url_for("instance_admin.edit_course", course_name=course["url"]),
                "namespaceSlug": course.get("namespace_slug") or "",
            }
            for course in context.get("courses", [])
        ],
    }


def serialize_namespace(context: Mapping[str, Any]) -> dict[str, Any]:
    namespace = context["namespace"]
    users = context.get("users", [])
    courses = context.get("courses", [])
    return {
        "namespace": _namespace(
            {
                "id": namespace.id,
                "name": namespace.name,
                "slug": namespace.slug,
                "description": namespace.description,
                "gitlab_group_id": namespace.gitlab_group_id,
                "users_count": len(users),
                "courses_count": len(courses),
            }
        ),
        "users": [
            {"id": user["id"], "username": user["username"], "rmsId": user["rms_id"], "role": user["role"]}
            for user in users
        ],
        "availableUsers": [
            {"id": user.user_id, "username": user.username, "rmsId": user.rms_id}
            for user in context.get("available_users", [])
        ],
        "courses": [
            {
                "id": course["id"],
                "name": course["name"],
                "href": course["url"],
                "owners": course["owners_string"],
                "status": course["status"],
                "gitlabGroup": course["gitlab_course_group"],
                "editHref": url_for("instance_admin.edit_course", course_name=course["name"]),
            }
            for course in courses
        ],
        "usersUrl": url_for("namespace_api.get_namespace_users", namespace_id=namespace.id),
        "roles": ROLES,
        "createCourseUrl": url_for("instance_admin.create_course", namespace_id=namespace.id),
        "namespacesUrl": url_for("instance_admin.namespaces_list"),
    }
