"""Explicit data contract for the course directory."""

from collections.abc import Mapping
from typing import Any

from flask import url_for


def serialize(context: Mapping[str, Any]) -> dict[str, Any]:
    """Use only courses and namespace rows already authorized by the root route."""
    courses = []
    for row in context.get("courses") or []:
        if not isinstance(row, Mapping):
            continue
        name, status, href = row.get("name"), row.get("status"), row.get("url")
        if not all(isinstance(value, str) for value in (name, status, href)):
            continue
        edit_href = row.get("edit_url") if row.get("can_edit") else None
        courses.append(
            {
                "name": name,
                "status": status,
                "href": href,
                "owners": "",
                "namespaceSlug": row.get("namespace_slug") if isinstance(row.get("namespace_slug"), str) else "",
                "editHref": edit_href if isinstance(edit_href, str) else None,
            }
        )

    admin_namespaces = []
    if context.get("can_create_courses"):
        for row in context.get("admin_namespaces") or []:
            if not isinstance(row, Mapping):
                continue
            identifier, name, href = row.get("id"), row.get("name"), row.get("url")
            if not isinstance(identifier, int) or not isinstance(name, str) or not isinstance(href, str):
                continue
            admin_namespaces.append(
                {
                    "id": identifier,
                    "name": name,
                    "href": href,
                    "slug": row.get("slug") if isinstance(row.get("slug"), str) else "",
                    "description": row.get("description") if isinstance(row.get("description"), str) else "",
                    "coursesCount": row.get("courses_count") if isinstance(row.get("courses_count"), int) else 0,
                    "usersCount": row.get("users_count") if isinstance(row.get("users_count"), int) else 0,
                }
            )

    status_order = context.get("status_order")
    visible_status_order = (
        [value for value in status_order if isinstance(value, str)] if isinstance(status_order, list) else []
    )
    can_create_courses = bool(context.get("can_create_courses"))
    is_instance_admin = bool(context.get("is_instance_admin"))
    return {
        "courses": courses,
        "statusOrder": visible_status_order,
        "adminNamespaces": admin_namespaces,
        "createCourseUrl": url_for("instance_admin.create_course") if can_create_courses else None,
        "instanceAdminUrl": url_for("instance_admin.instance_admin_panel") if is_instance_admin else None,
        "namespacesUrl": url_for("instance_admin.namespaces_list") if can_create_courses else None,
    }
