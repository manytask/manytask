import logging
import re
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

from .auth import handle_oauth_callback, requires_admin, requires_auth, requires_course_access, requires_ready
from .course import Course, CourseConfig, CourseStatus, get_current_time
from .main import CustomFlask
from .utils.flask import check_admin, get_courses
from .utils.generic import generate_token_hex

SESSION_VERSION = 1.5
CACHE_TIMEOUT_SECONDS = 3600

logger = logging.getLogger(__name__)
root_bp = Blueprint("root", __name__)
course_bp = Blueprint("course", __name__, url_prefix="/<course_name>")
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@root_bp.get("/healthcheck")
def healthcheck() -> ResponseReturnValue:
    return "OK", HTTPStatus.OK


@root_bp.route("/", methods=["GET"])
@requires_auth
def index() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    courses = get_courses(app)
    is_admin = check_admin(app)

    return render_template(
        "courses.html",
        course_favicon=app.favicon,
        manytask_version=app.manytask_version,
        courses=courses,
        is_admin=is_admin,
    )


@root_bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    oauth: OAuth = app.oauth

    redirect_uri = url_for("root.login_finish", _external=True)
    return oauth.remote_app.authorize_redirect(redirect_uri, state=url_for("root.index"))


@root_bp.route("/login_finish")
def login_finish() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    oauth: OAuth = app.oauth

    return handle_oauth_callback(oauth, app)


@root_bp.route("/logout")
def logout() -> ResponseReturnValue:
    session.pop("auth", None)
    return redirect(url_for("root.index"))


@course_bp.route("/", methods=["GET", "POST"])
@requires_course_access
def course_page(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    courses = get_courses(app)

    storage_api = app.storage_api

    if app.debug:
        username = "guest"
        student_repo = app.rms_api.get_url_for_repo(username=username, destination=course.gitlab_course_students_group)

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        username = session["auth"]["username"]

        student_repo = app.rms_api.get_url_for_repo(username=username, destination=course.gitlab_course_students_group)

        student_course_admin = storage_api.check_if_course_admin(course.course_name, username)

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
    tasks_scores = storage_api.get_scores(course.course_name, username)
    tasks_stats = storage_api.get_stats(course.course_name)
    allscores_url = url_for("course.show_database", course_name=course_name)
    match app.app_config.rms_backend:
        case "gitlab":
            student_ci_url = f"{student_repo}/pipelines"
        case "sourcecraft":
            student_ci_url = f"{student_repo}/cicd/runs"
        case _:
            raise ValueError(f"Invalid rms backend: {app.app_config.rms_backend}")

    return render_template(
        "tasks.html",
        task_base_url=app.rms_api.get_url_for_task_base(course.gitlab_course_public_repo, course.gitlab_default_branch),
        username=username,
        course_name=course.course_name,
        course_status=course.status,
        app=app,
        gitlab_url=app.rms_api.base_url,
        allscores_url=allscores_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=student_ci_url,
        manytask_version=app.manytask_version,
        task_url_template=course.task_url_template,
        links=course.links,
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(course.course_name, username),
        now=get_current_time(),
        task_stats=tasks_stats,
        course_favicon=app.favicon,
        is_course_admin=student_course_admin,
        cache_time=cache_delta,
        courses=courses,
        deadlines_type=course.deadlines_type,
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
            auth_backend=app.app_config.auth_backend,
        )

    # early exit for SourceCraft
    if app.config.get("AUTH_API") == "sourcecraft":
        return redirect(url_for("root.login"))

    # ----  register a new user ---- #

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as e:
        app.logger.error(f"CSRF validation failed: {e}")
        return render_template(
            "signup.html", course_favicon=app.favicon, manytask_version=app.manytask_version, error_message="CSRF Error"
        )

    try:
        if not secrets.compare_digest(request.form["password"], request.form["password2"]):
            raise Exception("Passwords don't match")

        # register user in gitlab
        username, firstname, lastname, email = map(
            lambda attr: request.form[attr].strip(), ("username", "firstname", "lastname", "email")
        )
        rms_user = app.rms_api.register_new_user(
            username,
            firstname,
            lastname,
            email,
            request.form["password"],
        )

        app.storage_api.create_user_if_not_exist(
            username,
            firstname,
            lastname,
            rms_user.id,
        )

    # render template with error... if error
    except Exception as e:
        logger.warning(f"User registration failed: {e}")
        return render_template(
            "signup.html",
            error_message=str(e),
            course_favicon=app.favicon,
            base_url=app.rms_api.base_url,
        )

    return redirect(url_for("root.login"))


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
        app.logger.error(f"CSRF validation failed: {e}")
        return render_template("create_project.html", error_message="CSRF Error")

    access_token: str = session["auth"]["access_token"]
    auth_user = app.auth_api.get_authenticated_user(access_token)
    user = app.storage_api.get_stored_user(auth_user.username)

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

    app.storage_api.sync_user_on_course(course.course_name, user.username, is_course_admin)

    try:
        app.rms_api.create_project(
            user.rms_identity, course.gitlab_course_students_group, course.gitlab_course_public_repo
        )
    except gitlab.GitlabError as ex:
        logger.error(f"Project creation failed: {ex.error_message}")
        return render_template("signup.html", error_message=ex.error_message, course_name=course.course_name)

    return redirect(url_for("course.course_page", course_name=course_name))


@course_bp.route("/not_ready")
def not_ready(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    course = app.storage_api.get_course(course_name)
    is_admin = check_admin(app)

    if course is None:
        return redirect(url_for("root.index"))

    if course.status != CourseStatus.CREATED:
        return redirect(url_for("course.course_page", course_name=course_name))

    return render_template(
        "not_ready.html", course_name=course.course_name, manytask_version=app.manytask_version, is_admin=is_admin
    )


@course_bp.get("/database")
@requires_course_access
def show_database(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    courses = get_courses(app)

    storage_api = app.storage_api

    if app.debug:
        username = "guest"
        student_repo = app.rms_api.get_url_for_repo(username=username, destination=course.gitlab_course_students_group)

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        username = session["auth"]["username"]

        student_repo = app.rms_api.get_url_for_repo(username=username, destination=course.gitlab_course_students_group)

        student_course_admin = storage_api.check_if_course_admin(course.course_name, username)

    scores = storage_api.get_scores(course.course_name, username)
    bonus_score = storage_api.get_bonus_score(course.course_name, username)

    return render_template(
        "database.html",
        course_name=course.course_name,
        scores=scores,
        bonus_score=bonus_score,
        username=username,
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
    )


@admin_bp.route("/courses/new", methods=["GET", "POST"])
@requires_admin
def create_course() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError as e:
            app.logger.error(f"CSRF validation failed: {e}")
            return render_template(
                "create_course.html", generated_token=generate_token_hex(24), error_message="CSRF Error"
            )

        settings = CourseConfig(
            course_name=request.form["unique_course_name"],
            gitlab_course_group=request.form["gitlab_course_group"],
            gitlab_course_public_repo=request.form["gitlab_course_public_repo"],
            gitlab_course_students_group=request.form["gitlab_course_students_group"],
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


@admin_bp.route("/courses/<course_name>/edit", methods=["GET", "POST"])
@requires_admin
def edit_course(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course = app.storage_api.get_course(course_name)

    if not course:
        flash("course not found!", category="course_not_found")
        return redirect(url_for("root.index"))

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError as e:
            app.logger.error(f"CSRF validation failed: {e}")
            return render_template("edit_course.html", error_message="CSRF Error")
        updated_settings = CourseConfig(
            course_name=course_name,
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
            return redirect(url_for("course.course_page", course_name=course_name))

        return render_template("edit_course.html", course=updated_settings, error_message="Error while updating course")

    return render_template("edit_course.html", course=course)


@admin_bp.route("/panel", methods=["GET", "POST"])
@requires_admin
def admin_panel() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    if request.method == "POST":
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError as e:
            app.logger.error(f"CSRF validation failed: {e}")
            return render_template("admin_panel.html", error_message="CSRF Error")

        action = request.form.get("action", "")
        username = request.form.get("username", "")
        current_admin = session["gitlab"]["username"]

        if action == "grant":
            app.storage_api.set_instance_admin_status(username, True)
            app.logger.warning(f"Admin {current_admin} granted admin status to {username}")
        elif action == "revoke":
            app.storage_api.set_instance_admin_status(username, False)
            app.logger.warning(f"Admin {current_admin} revoked admin status from {username}")
        else:
            app.logger.error(f"Unknown action: {action}")

        return redirect(url_for("admin.admin_panel"))

    users = app.storage_api.get_all_users()
    return render_template("admin_panel.html", courses=get_courses(app), users=users)


@root_bp.route("/update_profile", methods=["POST"])
@requires_auth
def update_profile() -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    def _validate_params(param: str) -> str | None:
        return param if (re.match(r"^[a-zA-Zа-яА-Я_-]{1,50}$", param) is not None) else None

    request_username = request.form.get("username", None)
    new_first_name = _validate_params(request.form.get("first_name", "").strip())
    new_last_name = _validate_params(request.form.get("last_name", "").strip())

    if request_username is None:
        abort(HTTPStatus.BAD_REQUEST)

    if app.debug:
        current_username = request_username
    else:
        current_username = session["gitlab"]["username"]

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as e:
        app.logger.error(f"CSRF validation failed: {e}")
        return render_template("courses.html", error_message="CSRF Error")

    if request_username != current_username and not app.storage_api.check_if_instance_admin(current_username):
        abort(HTTPStatus.FORBIDDEN)

    app.storage_api.update_user_profile(request_username, new_first_name, new_last_name)

    referrer = request.referrer
    if referrer:
        referrer_url = urlparse(referrer)
        current_url = urlparse(request.host_url)

        if referrer_url.netloc == current_url.netloc and referrer_url.scheme in ("http", "https"):
            return redirect(referrer)

    return redirect(url_for("root.index"))
