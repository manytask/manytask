"""Explicit data contracts for registration and course enrollment pages."""

from collections.abc import Mapping
from typing import Any

from flask import request, url_for


def _values(names: tuple[str, ...]) -> dict[str, str]:
    """Keep user-entered text after a failed POST, never credentials."""
    return {name: request.form[name] for name in names if name in request.form}


def serialize_signup(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "signup",
        "action": url_for("root.signup"),
        "values": _values(("username", "firstname", "lastname", "email")),
        "loginUrl": url_for("root.login"),
        "sourcecraftUrl": None,
        "invitationRequired": False,
    }


def serialize_signup_yandex_id(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "signup-yandex-id",
        "action": url_for("root.signup"),
        "values": {},
        "loginUrl": url_for("root.login"),
        "sourcecraftUrl": None,
        "invitationRequired": False,
    }


def serialize_signup_finish(context: Mapping[str, Any]) -> dict[str, Any]:
    sourcecraft_url = context.get("sourcecraft_url")
    return {
        "kind": "signup-finish",
        "action": url_for("root.signup_finish"),
        "values": _values(("firstname", "lastname")),
        "loginUrl": url_for("root.login"),
        "sourcecraftUrl": sourcecraft_url if isinstance(sourcecraft_url, str) else None,
        "sourcecraftNotRegistered": bool(context.get("sourcecraft_not_registered")),
        "invitationRequired": bool(context.get("sourcecraft_accept_invite_required")),
    }


def serialize_create_project(context: Mapping[str, Any]) -> dict[str, Any]:
    course_name = context.get("course_name")
    action = url_for("course.create_project", course_name=course_name) if isinstance(course_name, str) else request.path
    return {
        "kind": "create-project",
        "action": action,
        "values": {},
        "loginUrl": url_for("root.login"),
        "sourcecraftUrl": None,
        "invitationRequired": False,
    }
