"""Route-only payload for the grades page; rows come from the protected API."""

from collections.abc import Mapping
from typing import Any

from flask import url_for


def serialize(context: Mapping[str, Any]) -> dict[str, Any]:
    course_name = context["course_name"]
    return {
        "courseName": course_name,
        "readOnlyFields": list(context.get("readonly_fields", [])),
        "canEdit": bool(context.get("is_course_admin", False)),
        "urls": {
            "database": url_for("api.get_database", course_name=course_name),
            "updateScore": url_for("api.update_database", course_name=course_name),
            "updateComment": url_for("api.update_comment", course_name=course_name),
            "overrideGrade": url_for("api.override_grade", course_name=course_name),
            "clearGradeOverride": url_for("api.clear_grade_override", course_name=course_name),
        },
    }
