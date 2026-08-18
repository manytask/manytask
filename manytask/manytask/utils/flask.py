from flask import session, url_for

from manytask.course import CourseStatus
from manytask.main import CustomFlask


def get_courses(app: CustomFlask) -> list[dict[str, str | bool]]:
    username = "guest" if app.debug else session["manytask"]["username"]
    if app.debug or app.storage_api.check_if_instance_admin(username):
        courses_names = app.storage_api.get_all_courses_names_with_statuses()
        """
        Keeping the logic below for now, but this should be changed since namespace admin should see:
        - Courses from their namespaces
        - Courses they are registered to (not necessarily from their owned namespaces)
        """
    elif check_if_user_has_namespaces_to_admin(app):
        namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(username)
        namespace_courses = app.storage_api.get_courses_by_namespace_ids(namespace_admin_namespaces)
        course_admin_courses = app.storage_api.get_courses_where_course_admin(username)

        courses_dict = {name: status for name, status in namespace_courses}
        for name, status in course_admin_courses:
            if name not in courses_dict:
                courses_dict[name] = status

        courses_names = list[tuple[str, CourseStatus]](courses_dict.items())
    else:
        courses_names = app.storage_api.get_user_courses_names_with_statuses(username)

    is_instance_admin = app.debug or app.storage_api.check_if_instance_admin(username)

    courses_list = []
    for course_name, status in courses_names:
        course_obj = app.storage_api.get_course(course_name)
        namespace_slug = ""
        namespace_role: str | None = None
        namespace_id = course_obj.namespace_id if course_obj else None
        if namespace_id:
            try:
                namespace, namespace_role = app.storage_api.get_namespace_by_id(namespace_id, username)
                namespace_slug = namespace.slug
            except Exception:
                pass  # Namespace not found or no access

        courses_list.append(
            {
                "name": course_name,
                "status": status.value,
                "url": url_for("course.course_page", course_name=course_name),
                "namespace_slug": namespace_slug,
                "can_edit": can_edit_course(
                    app,
                    is_instance_admin=is_instance_admin,
                    namespace_id=namespace_id,
                    namespace_role=namespace_role,
                ),
                "edit_url": url_for("instance_admin.edit_course", course_name=course_name),
            }
        )

    return courses_list


def can_edit_course(
    app: CustomFlask,
    *,
    is_instance_admin: bool,
    namespace_id: int | None,
    namespace_role: str | None,
) -> bool:
    """Decide whether the current user may edit a course's settings.

    Pure decision function that mirrors the authorization enforced by the
    :func:`manytask.web.edit_course` route, so the Edit control shown in the UI
    never links to a page that would return HTTP 403. Being a *course* admin is
    intentionally not sufficient: a non-instance-admin may edit only a course
    that belongs to a namespace where they are a *namespace admin*.

    :param app: Flask application instance (debug mode grants edit access)
    :param is_instance_admin: whether the current user is an instance admin
    :param namespace_id: id of the course's namespace, or ``None``
    :param namespace_role: the user's role in that namespace, as returned by
        :meth:`StorageApi.get_namespace_by_id` (``None`` for instance admins or
        no access)
    :return: True if the user may edit the course
    """
    if app.debug:
        return True
    if is_instance_admin:
        return True
    return bool(namespace_id) and namespace_role == "namespace_admin"


def check_if_current_user_is_instance_admin(app: CustomFlask) -> bool:
    """Check whether the current session user is an instance admin.

    Session-aware Flask helper: resolves the username from the session (and
    returns ``True`` in debug mode), then delegates to the storage primitive
    :meth:`StorageApi.check_if_instance_admin`. Do not confuse it with that
    storage method, which takes an explicit ``username`` argument.

    :param app: Flask application instance
    :return: True if the current user is an instance admin
    """
    if app.debug:
        return True
    else:
        username = session["manytask"]["username"]
        return app.storage_api.check_if_instance_admin(username)


def check_if_current_user_is_namespace_admin(app: CustomFlask, course_name: str) -> bool:
    """Check if user is a namespace admin for the given course

    :param app: Flask application instance
    :param username: Manytask username
    :param course_name: Course to check for
    :return: True if user is an instance admin
    """
    if app.debug:
        return True
    else:
        username = session["manytask"]["username"]
        course = app.storage_api.get_course(course_name)
        if course and course.namespace_id:
            namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(username)
            if course.namespace_id in namespace_admin_namespaces:
                return True
        return False


def check_if_user_has_namespaces_to_admin(app: CustomFlask) -> bool:
    """The user can create course only if:
    - They are instance admin
    - There is a nemespace they are admin of.

    :param app: Flask application instance
    :return: True if user is a namespace admin
    """
    if app.debug:
        return True
    else:
        username = session["manytask"]["username"]
        namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(username)
        return len(namespace_admin_namespaces) > 0 or app.storage_api.check_if_instance_admin(username)


def get_user_roles(app: CustomFlask, username: str, course_name: str | None = None) -> list[str]:
    """Get list of roles for the user.

    Possible roles:
    - 'instance_admin': Instance Admin
    - 'namespace_admin': Namespace Admin (= Course Admin)
    - 'program_manager': Program Manager (student, hidden from results table)
    - 'student': Regular student

    :param app: Flask application instance
    :param username: manytask username
    :param course_name: Optional course name for course-specific roles
    :return: List of role strings
    """
    roles = []

    if app.storage_api.check_if_instance_admin(username):
        roles.append("instance_admin")

    if course_name:
        if check_if_current_user_is_namespace_admin(app, course_name=course_name):
            roles.append("namespace_admin")

        if app.storage_api.check_if_course_admin(course_name, username):
            if "namespace_admin" not in roles:
                roles.append("namespace_admin")

        roles.append("student")

    return roles


def has_role(username: str, required_roles: list[str] | str, app: CustomFlask, course_name: str | None = None) -> bool:
    """Check if user has at least one of the required roles.

    :param username: manytask username
    :param required_roles: Single role string or list of role strings
    :param app: Flask application instance
    :param course_name: Optional course name for course-specific roles
    :return: True if user has at least one of the required roles
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]

    user_roles = get_user_roles(app, username, course_name)
    return any(role in user_roles for role in required_roles)


def can_access_course(app: CustomFlask, username: str, course_name: str) -> bool:
    """Check if user can access a specific course.

    For Instance Admins: access to all courses
    For Namespace Admins: access to courses in their namespaces + courses where they are Course Admin
    For Students: access to courses they are enrolled in, or allow new students to register

    :param app: Flask application instance
    :param username: manytask username
    :param course_name: Course name to check access for
    :return: True if user can access the course
    """
    if app.storage_api.check_if_instance_admin(username):
        return True

    if app.storage_api.check_if_course_admin(course_name, username):
        return True

    if check_if_current_user_is_namespace_admin(app, course_name=course_name):
        course = app.storage_api.get_course(course_name)
        if course and course.namespace_id:
            namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(username)
            if course.namespace_id in namespace_admin_namespaces:
                return True

    if app.storage_api.check_user_on_course(course_name, username):
        return True

    return True
