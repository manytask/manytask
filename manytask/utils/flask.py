from flask import session, url_for

from manytask.main import CustomFlask


def get_courses(app: CustomFlask) -> list[dict[str, str]]:
    if app.debug:
        courses_names = app.storage_api.get_all_courses_names_with_statuses()
        rms_id = -1
    elif app.storage_api.check_if_instance_admin(session["profile"]["rms_id"]):
        courses_names = app.storage_api.get_all_courses_names_with_statuses()
        rms_id = session["profile"]["rms_id"]
    elif is_namespace_admin(app, session["profile"]["rms_id"]):
        rms_id = session["profile"]["rms_id"]
        namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(rms_id)
        namespace_courses = app.storage_api.get_courses_by_namespace_ids(namespace_admin_namespaces)
        course_admin_courses = app.storage_api.get_courses_where_course_admin(rms_id)

        courses_dict = {name: status for name, status in namespace_courses}
        for name, status in course_admin_courses:
            if name not in courses_dict:
                courses_dict[name] = status

        courses_names = list(courses_dict.items())
    else:
        rms_id = session["profile"]["rms_id"]
        courses_names = app.storage_api.get_user_courses_names_with_statuses(rms_id)

    courses_list = []
    for course_name, status in courses_names:
        course_obj = app.storage_api.get_course(course_name)
        namespace_slug = ""
        if course_obj and course_obj.namespace_id:
            try:
                namespace, _ = app.storage_api.get_namespace_by_id(course_obj.namespace_id, rms_id)
                namespace_slug = namespace.slug
            except Exception:
                pass  # Namespace not found or no access

        courses_list.append(
            {
                "name": course_name,
                "status": status.value,
                "url": url_for("course.course_page", course_name=course_name),
                "namespace_slug": namespace_slug,
            }
        )

    return courses_list


def check_instance_admin(app: CustomFlask) -> bool:
    if app.debug:
        return True
    else:
        rms_id = session["profile"]["rms_id"]
        return app.storage_api.check_if_instance_admin(rms_id)


def is_namespace_admin(app: CustomFlask, rms_id: int) -> bool:
    """Check if user is a Namespace Admin (Owner of any namespace or has Namespace Admin role).

    :param app: Flask application instance
    :param rms_id: user's RMS ID
    :return: True if user is a namespace admin
    """
    namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(rms_id)
    return len(namespace_admin_namespaces) > 0


def get_user_roles(app: CustomFlask, rms_id: int, course_name: str | None = None) -> list[str]:
    """Get list of roles for the user.

    Possible roles:
    - 'instance_admin': Instance Admin
    - 'namespace_admin': Namespace Admin (= Course Admin)
    - 'program_manager': Program Manager (student, hidden from results table)
    - 'student': Regular student

    :param app: Flask application instance
    :param rms_id: user's RMS ID
    :param course_name: Optional course name for course-specific roles
    :return: List of role strings
    """
    roles = []

    if app.storage_api.check_if_instance_admin(rms_id):
        roles.append("instance_admin")

    if is_namespace_admin(app, rms_id):
        roles.append("namespace_admin")

    if course_name and app.storage_api.check_if_course_admin(course_name, rms_id):
        if "namespace_admin" not in roles:
            roles.append("namespace_admin")

    if course_name:
        roles.append("student")

    return roles


def has_role(rms_id: int, required_roles: list[str] | str, app: CustomFlask, course_name: str | None = None) -> bool:
    """Check if user has at least one of the required roles.

    :param rms_id: user's RMS ID
    :param required_roles: Single role string or list of role strings
    :param app: Flask application instance
    :param course_name: Optional course name for course-specific roles
    :return: True if user has at least one of the required roles
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]

    user_roles = get_user_roles(app, rms_id, course_name)
    return any(role in user_roles for role in required_roles)


def can_access_course(app: CustomFlask, rms_id: int, course_name: str) -> bool:
    """Check if user can access a specific course.

    For Instance Admins: access to all courses
    For Namespace Admins: access to courses in their namespaces + courses where they are Course Admin
    For Students: access to courses they are enrolled in, or allow new students to register

    :param app: Flask application instance
    :param rms_id: user's RMS ID
    :param course_name: Course name to check access for
    :return: True if user can access the course
    """
    if app.storage_api.check_if_instance_admin(rms_id):
        return True

    if app.storage_api.check_if_course_admin(course_name, rms_id):
        return True

    if is_namespace_admin(app, rms_id):
        course = app.storage_api.get_course(course_name)
        if course and course.namespace_id:
            namespace_admin_namespaces = app.storage_api.get_namespace_admin_namespaces(rms_id)
            if course.namespace_id in namespace_admin_namespaces:
                return True

    if app.storage_api.check_user_on_course(course_name, rms_id):
        return True

    return True
