import logging
import secrets
from datetime import datetime, timedelta
from http import HTTPStatus

import gitlab
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from flask_wtf.csrf import validate_csrf
from wtforms import ValidationError

from .auth import requires_admin, requires_auth, requires_course_access, requires_ready
from .course import Course, CourseConfig, get_current_time
from .database_utils import get_database_table_data
from .main import CustomFlask
from .utils import generate_token_hex

SESSION_VERSION = 1.5


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

    if app.debug:
        courses_names = app.storage_api.get_all_courses_names()

    else:
        student_id = session["gitlab"]["user_id"]
        student = app.gitlab_api.get_student(student_id)

        courses_names = app.storage_api.get_user_courses_names(student)

    courses = [
        {
            "name": course_name,
            "url": url_for("course.course_page", course_name=course_name),
        }
        for course_name in courses_names
    ]

    return render_template(
        "courses.html",
        course_favicon=app.favicon,
        manytask_version=app.manytask_version,
        courses=courses,
    )


@root_bp.route("/login", methods=["GET", "POST"])
@requires_auth
def login() -> ResponseReturnValue:
    return redirect(url_for("root.index"))


@root_bp.route("/logout")
def logout() -> ResponseReturnValue:
    session.pop("gitlab", None)
    return redirect(url_for("root.index"))


@course_bp.route("/", methods=["GET", "POST"])
@requires_course_access
def course_page(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

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
        student_id = session["gitlab"]["user_id"]

        student_repo = app.rms_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        student = app.gitlab_api.get_student(user_id=student_id)
        stored_user = storage_api.get_stored_user(course.course_name, student)

        student_course_admin = stored_user.course_admin

    # update cache if more than 1h passed or in debug mode
    try:
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp(course.course_name)))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time
    except ValueError:
        cache_delta = timedelta(days=365)

    hours_in_seconds = 3600
    if app.debug or cache_delta.total_seconds() > hours_in_seconds:
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
    )


@course_bp.route("/signup", methods=["GET", "POST"])
@requires_ready
def signup(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            course_name=course.course_name,
            course_favicon=app.favicon,
            manytask_version=app.manytask_version,
        )

    # ----  register a new user ---- #

    try:
        if not secrets.compare_digest(request.form["secret"], course.registration_secret):
            raise Exception("Invalid registration secret")
        if not secrets.compare_digest(request.form["password"], request.form["password2"]):
            raise Exception("Passwords don't match")

        # register user in gitlab
        app.rms_api.register_new_user(
            request.form["username"].strip(),
            request.form["firstname"].strip(),
            request.form["lastname"].strip(),
            request.form["email"].strip(),
            request.form["password"],
        )

    # render template with error... if error
    except Exception as e:
        logger.warning(f"User registration failed: {e}")
        return render_template(
            "signup.html",
            error_message=str(e),
            course_name=course.course_name,
            course_favicon=app.favicon,
            base_url=app.rms_api.base_url,
        )

    return redirect(url_for("course.create_project", course_name=course.course_name))


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

    if not secrets.compare_digest(request.form["secret"], course.registration_secret):
        return render_template(
            "create_project.html",
            error_message="Invalid secret",
            course_name=course.course_name,
            course_favicon=app.favicon,
            base_url=app.rms_api.base_url,
        )

    gitlab_access_token: str = session["gitlab"]["access_token"]
    student = app.gitlab_api.get_authenticated_student(gitlab_access_token)
    app.storage_api.create_user_if_not_exist(student, course.course_name)

    app.storage_api.sync_stored_user(
        course.course_name,
        student,
        app.rms_api.get_url_for_repo(student.username, course.gitlab_course_students_group),
        app.gitlab_api.check_is_course_admin(student.id, course.gitlab_course_group),
    )

    # Create use if needed
    try:
        app.rms_api.create_project(student, course.gitlab_course_students_group, course.gitlab_course_public_repo)
    except gitlab.GitlabError as ex:
        logger.error(f"Project creation failed: {ex.error_message}")
        return render_template("signup.html", error_message=ex.error_message, course_name=course.course_name)

    return redirect(url_for("course.course_page", course_name=course_name))


@course_bp.route("/not_ready")
def not_ready(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore

    course = app.storage_api.get_course(course_name)

    if course is None:
        return redirect(url_for("root.index"))

    if course.is_ready:
        return redirect(url_for("course.course_page", course_name=course_name))

    return render_template(
        "not_ready.html",
        course_name=course.course_name,
        manytask_version=app.manytask_version,
    )


@course_bp.get("/database")
@requires_course_access
def show_database(course_name: str) -> ResponseReturnValue:
    app: CustomFlask = current_app  # type: ignore
    course: Course = app.storage_api.get_course(course_name)  # type: ignore

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
        student_id = session["gitlab"]["user_id"]

        student_repo = app.rms_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        student = app.gitlab_api.get_student(user_id=student_id)
        stored_user = storage_api.get_stored_user(course.course_name, student)

        student_course_admin = stored_user.course_admin

    scores = storage_api.get_scores(course.course_name, student_username)
    bonus_score = storage_api.get_bonus_score(course.course_name, student_username)
    table_data = get_database_table_data(app, course.course_name)

    return render_template(
        "database.html",
        table_data=table_data,
        course_name=course.course_name,
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
            is_ready=False,
            task_url_template="",
            links={},
        )

        if app.storage_api.create_course(settings):
            return redirect(url_for("course.course_page", course_name=settings.course_name))

        return render_template(
            "create_course.html",
            generated_token=generate_token_hex(24),
            error_message=f"Курс с названием '{settings.course_name}' уже существует",
        )

    return render_template(
        "create_course.html",
        generated_token=generate_token_hex(24),
    )
