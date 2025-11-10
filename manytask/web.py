import logging
import secrets
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import urlparse

import gitlab
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from flask_wtf.csrf import validate_csrf
from wtforms import ValidationError

from manytask.course import ManytaskDeadlinesType

from .abstract import ClientProfile
from .auth import (
    handle_oauth_callback,
    redirect_to_login_with_bad_session,
    requires_instance_admin,
    requires_instance_or_namespace_admin,
    requires_auth,
    requires_course_access,
    requires_ready,
    role_required,
    set_client_profile_session,
    valid_client_profile_session,
    valid_gitlab_session,
)
from .course import Course, CourseConfig, CourseStatus, get_current_time
from .main import CustomFlask
from .utils.flask import check_instance_admin, get_courses, has_role
from .utils.generic import generate_token_hex, sanitize_log_data, validate_name

SESSION_VERSION = 1.5
CACHE_TIMEOUT_SECONDS = 3600

logger = logging.getLogger(__name__)
root_bp = Blueprint("root", __name__)
course_bp = Blueprint("course", __name__, url_prefix="/<course_name>")
instance_admin_bp = Blueprint("instance_admin", __name__, url_prefix="/instance_admin")


@root_bp.get("/healthcheck")
def healthcheck() -> ResponseReturnValue:
    return "OK", HTTPStatus.OK


@root_bp.route("/", methods=["GET"])
@requires_auth
def index() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    courses = get_courses(app)
    is_instance_admin = check_instance_admin(app)
    
    # Check if user is a namespace admin
    if app.debug:
        is_namespace_admin_flag = True
    else:
        from .utils.flask import is_namespace_admin
        is_namespace_admin_flag = is_namespace_admin(app, session["profile"]["username"])

    return render_template(
        "courses.html",
        course_favicon=app.favicon,
        manytask_version=app.manytask_version,
        courses=courses,
        is_instance_admin=is_instance_admin,
        is_namespace_admin=is_namespace_admin_flag,
    )


@root_bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    oauth: OAuth = app.oauth

    redirect_uri = url_for("root.login_finish", _external=True)
    return oauth.gitlab.authorize_redirect(redirect_uri)


@root_bp.route("/login_finish")
def login_finish() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    oauth: OAuth = app.oauth

    result = handle_oauth_callback(oauth, app)
    if "gitlab" in session:
        logger.info("User %s successfully authenticated", session["gitlab"]["username"])
    return result


@root_bp.route("/logout")
def logout() -> ResponseReturnValue:
    session.pop("gitlab", None)
    return redirect(url_for("root.index"))


@course_bp.route("/", methods=["GET", "POST"])
@requires_course_access
def course_page(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    courses = get_courses(app)

    storage_api = app.storage_api

    if app.debug:
        student_username = "guest"
        student_repo = app.rms_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student_username = session["gitlab"]["username"]

        student_repo = app.rms_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )
        student_course_admin = storage_api.check_if_course_admin(course.course_name, session["profile"]["username"])

    # update cache if more than 1h passed or in debug mode
    try:
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp(course.course_name)))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time
    except ValueError:
        cache_delta = timedelta(days=365)

    if app.debug or cache_delta.total_seconds() > CACHE_TIMEOUT_SECONDS:
        storage_api.update_cached_scores(course.course_name)
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp(course.course_name)))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time

    # get scores
    tasks_scores = storage_api.get_scores(course.course_name, student_username)
    tasks_stats = storage_api.get_stats(course.course_name)
    allscores_url = url_for("course.show_database", course_name=course_name)

    return render_template(
        "tasks.html",
        task_base_url=app.rms_api.get_url_for_task_base(course.gitlab_course_public_repo, course.gitlab_default_branch),
        username=student_username,
        course_name=course.course_name,
        course_status=course.status,
        app=app,
        gitlab_url=app.rms_api.base_url,
        allscores_url=allscores_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        manytask_version=app.manytask_version,
        task_url_template=course.task_url_template,
        links=course.links,
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(course.course_name, student_username),
        now=get_current_time(),
        task_stats=tasks_stats,
        course_favicon=app.favicon,
        is_course_admin=student_course_admin,
        cache_time=cache_delta,
        courses=courses,
        deadlines_type=course.deadlines_type,
        has_role=has_role,
    )


@root_bp.route("/signup", methods=["GET", "POST"])
def signup() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            course_favicon=app.favicon,
            manytask_version=app.manytask_version,
        )

    # ----  register a new user ---- #

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as e:
        app.logger.error("CSRF validation failed: %s", e)
        return render_template(
            "signup.html", course_favicon=app.favicon, manytask_version=app.manytask_version, error_message="CSRF Error"
        )

    try:
        if not secrets.compare_digest(request.form["password"], request.form["password2"]):
            raise Exception("Passwords don't match")

        username, firstname, lastname, email = map(
            lambda attr: request.form[attr].strip(), ("username", "firstname", "lastname", "email")
        )

        validated_firstname = validate_name(firstname)
        validated_lastname = validate_name(lastname)
        if validated_firstname is None or validated_lastname is None:
            raise Exception("Firstname and lastname must be 1-50 characters and contain only letters or hyphens.")

        # register user in gitlab
        rms_user = app.rms_api.register_new_user(
            username,
            validated_firstname,
            validated_lastname,
            email,
            request.form["password"],
        )

        app.storage_api.update_or_create_user(
            username,
            validated_firstname,
            validated_lastname,
            rms_user.id,
        )

    # render template with error... if error
    except Exception as e:
        logger.warning("User registration failed: %s", e)
        return render_template(
            "signup.html",
            error_message=str(e),
            course_favicon=app.favicon,
            base_url=app.rms_api.base_url,
        )

    return redirect(url_for("root.login"))


@root_bp.route("/signup_finish", methods=["GET", "POST"])
def signup_finish() -> ResponseReturnValue:  # noqa: PLR0911
    app: CustomFlask = current_app  # type: ignore

    if not valid_gitlab_session(session):
        return redirect_to_login_with_bad_session()

    if valid_client_profile_session(session):
        logger.warning("User already has username=%s in session", session["profile"]["username"])
        return redirect(url_for("root.index"))

    stored_user_or_none = app.storage_api.get_stored_user_by_rms_id(session["gitlab"]["user_id"])
    if stored_user_or_none is not None:
        session.setdefault("profile", {}).update(
            set_client_profile_session(ClientProfile(session["gitlab"]["username"]))
        )
        return redirect(url_for("root.index"))

    if request.method == "GET":
        return render_template(
            "signup_finish.html",
            course_favicon=app.favicon,
            manytask_version=app.manytask_version,
        )

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as e:
        app.logger.error("CSRF validation failed: %s", e)
        return render_template(
            "signup.html", course_favicon=app.favicon, manytask_version=app.manytask_version, error_message="CSRF Error"
        )

    firstname = validate_name(request.form.get("firstname", "").strip())
    lastname = validate_name(request.form.get("lastname", "").strip())
    if firstname is None or lastname is None:
        return render_template(
            "signup_finish.html",
            course_favicon=app.favicon,
            manytask_version=app.manytask_version,
            error_message="Firstname and lastname must be 1-50 characters and contain only letters or hyphens.",
        )

    app.storage_api.update_or_create_user(
        session["gitlab"]["username"], firstname, lastname, session["gitlab"]["user_id"]
    )
    session.setdefault("profile", {}).update(set_client_profile_session(ClientProfile(session["gitlab"]["username"])))
    return redirect(url_for("root.index"))


@course_bp.route("/create_project", methods=["GET", "POST"])
@requires_ready
@requires_auth
def create_project(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    if request.method == "GET":
        return render_template(
            "create_project.html",
            course_name=course.course_name,
            course_favicon=app.favicon,
            base_url=app.rms_api.base_url,
        )

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as e:
        app.logger.error("CSRF validation failed: %s", e)
        return render_template("create_project.html", error_message="CSRF Error")

    gitlab_access_token: str = session["gitlab"]["access_token"]
    rms_user = app.rms_api.get_authenticated_rms_user(gitlab_access_token)

    # Set user to be course admin if they provided course token as a secret
    is_course_admin: bool = secrets.compare_digest(request.form["secret"], course.token)
    if not is_course_admin and not secrets.compare_digest(request.form["secret"], course.registration_secret):
        return render_template(
            "create_project.html",
            error_message="Invalid secret",
            course_name=course.course_name,
            course_favicon=app.favicon,
            base_url=app.rms_api.base_url,
        )

    app.storage_api.sync_user_on_course(course.course_name, session["profile"]["username"], is_course_admin)

    # Create use if needed
    try:
        app.rms_api.create_project(rms_user, course.gitlab_course_students_group, course.gitlab_course_public_repo)
        logger.info("Successfully created project for user %s in course %s", rms_user.username, course.course_name)
    except gitlab.GitlabError as ex:
        logger.error("Project creation failed: %s", ex.error_message)
        return render_template("signup.html", error_message=ex.error_message, course_name=course.course_name)

    return redirect(url_for("course.course_page", course_name=course_name))


@course_bp.route("/not_ready")
def not_ready(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    course = app.storage_api.get_course(course_name)
    is_instance_admin = check_instance_admin(app)

    if course is None:
        return redirect(url_for("root.index"))

    if course.status != CourseStatus.CREATED:
        return redirect(url_for("course.course_page", course_name=course_name))

    return render_template(
        "not_ready.html", course_name=course.course_name, manytask_version=app.manytask_version, is_instance_admin=is_instance_admin
    )


@course_bp.get("/database")
@requires_course_access
def show_database(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    courses = get_courses(app)

    storage_api = app.storage_api

    if app.debug:
        student_username = "guest"
        student_repo = app.rms_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student_username = session["gitlab"]["username"]

        student_repo = app.rms_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        student_course_admin = storage_api.check_if_course_admin(course.course_name, session["profile"]["username"])

    scores = storage_api.get_scores(course.course_name, student_username)
    bonus_score = storage_api.get_bonus_score(course.course_name, student_username)

    return render_template(
        "database.html",
        course_name=course.course_name,
        course_status=course.status,
        scores=scores,
        bonus_score=bonus_score,
        username=student_username,
        is_course_admin=student_course_admin,
        app=app,
        course_favicon=app.favicon,
        readonly_fields=["username", "total_score"],  # Cannot be edited in database web viewer
        links=course.links,
        gitlab_url=app.rms_api.base_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        manytask_version=app.manytask_version,
        courses=courses,
        has_role=has_role,
    )


@instance_admin_bp.route("/courses/new", methods=["GET", "POST"])
@requires_instance_or_namespace_admin
def create_course() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError as e:
            app.logger.error("CSRF validation failed: %s", e)
            return render_template(
                "create_course.html", generated_token=generate_token_hex(24), error_message="CSRF Error"
            )

        namespace_id_str = request.form.get("namespace_id", "").strip()
        if not namespace_id_str:
            return render_template(
                "create_course.html",
                generated_token=generate_token_hex(24),
                error_message="Namespace is required",
            )

        try:
            namespace_id = int(namespace_id_str)
        except ValueError:
            return render_template(
                "create_course.html",
                generated_token=generate_token_hex(24),
                error_message="Invalid namespace ID",
            )

        username = session["gitlab"]["username"]
        is_instance_admin = app.storage_api.check_if_instance_admin(username)
        
        try:
            namespace, role = app.storage_api.get_namespace_by_id(namespace_id, username)
        except PermissionError:
            logger.warning("User %s attempted to create course with namespace id=%s without access", username, namespace_id)
            return render_template(
                "create_course.html",
                generated_token=generate_token_hex(24),
                error_message="Access denied to selected namespace",
            )
        except Exception as e:
            logger.error("Error fetching namespace id=%s: %s", namespace_id, str(e))
            return render_template(
                "create_course.html",
                generated_token=generate_token_hex(24),
                error_message="Selected namespace not found",
            )

        if not is_instance_admin and role != "namespace_admin":
            logger.warning(
                "User %s with role %s attempted to create course in namespace id=%s",
                username,
                role,
                namespace_id,
            )
            return render_template(
                "create_course.html",
                generated_token=generate_token_hex(24),
                error_message="Only Instance Admin or Namespace Admin can create courses",
            )

        course_name = request.form["unique_course_name"].strip()
        gitlab_course_group = request.form["gitlab_course_group"].strip()
        gitlab_course_public_repo = request.form["gitlab_course_public_repo"].strip()
        gitlab_course_students_group = request.form["gitlab_course_students_group"].strip()
        
        try:
            logger.info("Creating GitLab course group: %s", gitlab_course_group)
            course_group_id = app.rms_api.create_course_group(
                parent_group_id=namespace.gitlab_group_id,
                course_name=course_name,
                course_slug=gitlab_course_group.split("/")[-1] if "/" in gitlab_course_group else gitlab_course_group,
            )
            logger.info("Created course group with id=%s", course_group_id)
            
            logger.info("Creating public repo: %s", gitlab_course_public_repo)
            app.rms_api.create_public_repo(gitlab_course_group, gitlab_course_public_repo)
            logger.info("Created public repo")
            
            logger.info("Creating students group: %s", gitlab_course_students_group)
            app.rms_api.create_students_group(gitlab_course_students_group, parent_group_id=course_group_id)
            logger.info("Created students group")
            
        except Exception as e:
            logger.error("Failed to create GitLab resources: %s", str(e), exc_info=True)
            return render_template(
                "create_course.html",
                generated_token=generate_token_hex(24),
                error_message=f"Failed to create GitLab resources: {str(e)}",
            )

        settings = CourseConfig(
            course_name=course_name,
            namespace_id=namespace_id,
            gitlab_course_group=gitlab_course_group,
            gitlab_course_public_repo=gitlab_course_public_repo,
            gitlab_course_students_group=gitlab_course_students_group,
            gitlab_default_branch=request.form["gitlab_default_branch"],
            registration_secret=request.form["registration_secret"],
            token=request.form["token"],
            show_allscores=request.form.get("show_allscores", "off") == "on",
            status=CourseStatus.CREATED,
            task_url_template="",
            links={},
            deadlines_type=ManytaskDeadlinesType.HARD,
        )

        if app.storage_api.create_course(settings):
            logger.info("Successfully created new course: %s", settings.course_name)
            return redirect(url_for("course.course_page", course_name=settings.course_name))

        return render_template(
            "create_course.html",
            generated_token=generate_token_hex(24),
            error_message=f"Course '{settings.course_name}' already exists.",
        )

    return render_template(
        "create_course.html",
        generated_token=generate_token_hex(24),
    )


@instance_admin_bp.route("/courses/<course_name>/edit", methods=["GET", "POST"])
@requires_instance_or_namespace_admin
def edit_course(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course = app.storage_api.get_course(course_name)

    if not course:
        flash("course not found!", category="course_not_found")
        return redirect(url_for("root.index"))
    
    if not app.debug:
        username = session["profile"]["username"]
        is_instance_admin = app.storage_api.check_if_instance_admin(username)
        
        if not is_instance_admin:
            if course.namespace_id:
                try:
                    namespace, role = app.storage_api.get_namespace_by_id(course.namespace_id, username)
                    if role != "namespace_admin":
                        logger.warning(
                            "User %s with role %s attempted to edit course %s in namespace %d",
                            username,
                            role,
                            course_name,
                            course.namespace_id,
                        )
                        abort(HTTPStatus.FORBIDDEN)
                except PermissionError:
                    logger.warning(
                        "User %s attempted to edit course %s without access to namespace %d",
                        username,
                        course_name,
                        course.namespace_id,
                    )
                    abort(HTTPStatus.FORBIDDEN)
            else:
                logger.warning("User %s attempted to edit course %s without namespace", username, course_name)
                abort(HTTPStatus.FORBIDDEN)

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError as e:
            app.logger.error("CSRF validation failed: %s", e)
            return render_template("edit_course.html", error_message="CSRF Error")
        updated_settings = CourseConfig(
            course_name=course_name,
            namespace_id=course.namespace_id,
            gitlab_course_group=request.form["gitlab_course_group"],
            gitlab_course_public_repo=request.form["gitlab_course_public_repo"],
            gitlab_course_students_group=request.form["gitlab_course_students_group"],
            gitlab_default_branch=request.form["gitlab_default_branch"],
            registration_secret=request.form["registration_secret"],
            token=course.token,
            show_allscores=request.form.get("show_allscores", "off") == "on",
            status=CourseStatus(request.form["course_status"]),
            task_url_template=course.task_url_template,
            links=course.links,
            deadlines_type=course.deadlines_type,
        )

        if app.storage_api.edit_course(updated_settings):
            logger.info("Successfully updated course settings for: %s", sanitize_log_data(course_name))
            return redirect(url_for("course.course_page", course_name=course_name))

        return render_template("edit_course.html", course=updated_settings, error_message="Error while updating course")

    return render_template("edit_course.html", course=course)


@instance_admin_bp.route("/", methods=["GET"])
@requires_auth
def instance_admin_index() -> ResponseReturnValue:
    """Root instance admin page that redirects based on user role.
    
    Instance Admin -> /instance_admin/panel
    Namespace Admin -> /instance_admin/namespaces
    """
    app: CustomFlask = current_app  # type: ignore
    
    if app.debug:
        return redirect(url_for("instance_admin.instance_admin_panel"))
    
    username = session["profile"]["username"]
    is_instance_admin = app.storage_api.check_if_instance_admin(username)
    
    if is_instance_admin:
        logger.info("Instance Admin %s accessing instance admin root, redirecting to panel", username)
        return redirect(url_for("instance_admin.instance_admin_panel"))
    
    from .utils.flask import is_namespace_admin
    is_namespace_admin_flag = is_namespace_admin(app, username)
    
    if is_namespace_admin_flag:
        logger.info("Namespace Admin %s accessing instance admin root, redirecting to namespaces", username)
        return redirect(url_for("instance_admin.namespaces_list"))
    
    logger.warning("User %s attempted to access instance admin without privileges", username)
    abort(HTTPStatus.FORBIDDEN)


@instance_admin_bp.route("/panel", methods=["GET", "POST"])
@role_required(['instance_admin'])
def instance_admin_panel() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError as e:
            app.logger.error("CSRF validation failed: %s", e)
            return render_template("instance_admin_panel.html", error_message="CSRF Error")

        action = request.form.get("action", "")
        username = request.form.get("username", "")
        current_instance_admin = session["gitlab"]["username"]

        if action == "grant":
            app.storage_api.set_instance_admin_status(username, True)
            app.logger.warning("Instance Admin %s granted instance admin status to %s", current_instance_admin, username)
        elif action == "revoke":
            app.storage_api.set_instance_admin_status(username, False)
            app.logger.warning("Instance Admin %s revoked instance admin status from %s", current_instance_admin, username)
        else:
            app.logger.error("Unknown action: %s", action)

        return redirect(url_for("instance_admin.instance_admin_panel"))

    users = app.storage_api.get_all_users()
    
    namespaces = app.storage_api.get_all_namespaces()
    namespaces_data = []
    for namespace in namespaces:
        users_count = len(app.storage_api.get_namespace_users(namespace.id))
        namespaces_data.append({
            'id': namespace.id,
            'name': namespace.name,
            'slug': namespace.slug,
            'description': namespace.description or '',
            'gitlab_group_id': namespace.gitlab_group_id,
            'users_count': users_count,
        })
    
    return render_template("instance_admin_panel.html", courses=get_courses(app), users=users, namespaces=namespaces_data)


@root_bp.route("/update_profile", methods=["POST"])
@requires_auth
def update_profile() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    request_username = request.form.get("username", None)
    new_first_name = validate_name(request.form.get("first_name", "").strip())
    new_last_name = validate_name(request.form.get("last_name", "").strip())

    if request_username is None:
        abort(HTTPStatus.BAD_REQUEST)

    if app.debug:
        current_username = request_username
    else:
        current_username = session["gitlab"]["username"]

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as e:
        app.logger.error("CSRF validation failed: %s", e)
        return render_template("courses.html", error_message="CSRF Error")

    if request_username != current_username and not app.storage_api.check_if_instance_admin(current_username):
        abort(HTTPStatus.FORBIDDEN)

    app.storage_api.update_user_profile(request_username, new_first_name, new_last_name)
    logger.info("Successfully updated profile for user: %s", sanitize_log_data(request_username))

    referrer = request.referrer
    if referrer:
        referrer_url = urlparse(referrer)
        current_url = urlparse(request.host_url)

        if referrer_url.netloc == current_url.netloc and referrer_url.scheme in ("http", "https"):
            return redirect(referrer)

    return redirect(url_for("root.index"))


@instance_admin_bp.route("/namespaces", methods=["GET"])
@role_required(['namespace_admin', 'instance_admin'])
def namespaces_list() -> ResponseReturnValue:
    """Display list of namespaces accessible to the user.
    
    Instance Admin sees all namespaces.
    Namespace Admin sees only their namespaces.
    """
    app: CustomFlask = current_app  # type: ignore
    
    username = session["gitlab"]["username"]
    is_instance_admin = app.storage_api.check_if_instance_admin(username)
    
    if is_instance_admin:
        logger.info("Instance Admin %s accessing all namespaces", username)
        namespaces = app.storage_api.get_all_namespaces()
        namespace_data = []
        
        for ns in namespaces:
            users_count = len(app.storage_api.get_namespace_users(ns.id))
            courses = app.storage_api.get_namespace_courses(ns.id)
            courses_count = len(courses)
            
            namespace_data.append({
                'id': ns.id,
                'name': ns.name,
                'slug': ns.slug,
                'description': ns.description or '',
                'gitlab_group_id': ns.gitlab_group_id,
                'users_count': users_count,
                'courses_count': courses_count,
            })
    else:
        logger.info("Namespace Admin %s accessing their namespaces", username)
        user_namespaces = app.storage_api.get_user_namespaces(username)
        namespace_data = []
        
        for ns, role in user_namespaces:
            if role == "namespace_admin":
                users_count = len(app.storage_api.get_namespace_users(ns.id))
                courses = app.storage_api.get_namespace_courses(ns.id)
                courses_count = len(courses)
                
                namespace_data.append({
                    'id': ns.id,
                    'name': ns.name,
                    'slug': ns.slug,
                    'description': ns.description or '',
                    'gitlab_group_id': ns.gitlab_group_id,
                    'users_count': users_count,
                    'courses_count': courses_count,
                })
    
    return render_template(
        "namespaces_list.html",
        namespaces=namespace_data,
        is_instance_admin=is_instance_admin,
        manytask_version=app.manytask_version,
    )


@instance_admin_bp.route("/namespaces/<int:namespace_id>", methods=["GET"])
@role_required(['namespace_admin', 'instance_admin'])
def namespace_panel(namespace_id: int) -> ResponseReturnValue:
    """Display detailed panel for a specific namespace.
    
    Instance Admin can access any namespace.
    Namespace Admin can only access their own namespaces.
    """
    app: CustomFlask = current_app  # type: ignore
    
    username = session["gitlab"]["username"]
    is_instance_admin = app.storage_api.check_if_instance_admin(username)
    
    try:
        namespace, user_role = app.storage_api.get_namespace_by_id(namespace_id, username)
    except PermissionError:
        logger.warning("User %s attempted to access namespace %d without permission", username, namespace_id)
        abort(HTTPStatus.FORBIDDEN)
    except Exception as e:
        logger.error("Error accessing namespace %d: %s", namespace_id, str(e))
        abort(HTTPStatus.NOT_FOUND)
    
    if not is_instance_admin and user_role != "namespace_admin":
        logger.warning(
            "User %s with role %s attempted to access namespace %d",
            username,
            user_role,
            namespace_id,
        )
        abort(HTTPStatus.FORBIDDEN)
    
    namespace_users = app.storage_api.get_namespace_users(namespace_id)
    
    users_data = []
    for user_id, role in namespace_users:
        try:
            user = app.storage_api.get_stored_user_by_id(user_id)
            if user:
                users_data.append({
                    'id': user_id,
                    'username': user.username,
                    'rms_id': user.rms_id,
                    'role': role,
                })
        except Exception as e:
            logger.warning("Could not get user info for user_id=%s: %s", user_id, str(e))
    
    courses = app.storage_api.get_namespace_courses(namespace_id)
    
    for course in courses:
        course['url'] = url_for('course.course_page', course_name=course['name'])
        course['owners_string'] = ', '.join(course['owners']) if course['owners'] else 'No owners'
    
    return render_template(
        "namespace_panel.html",
        namespace=namespace,
        users=users_data,
        courses=courses,
        is_instance_admin=is_instance_admin,
        manytask_version=app.manytask_version,
    )
