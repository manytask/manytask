import logging
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast
from zoneinfo import ZoneInfo

import flask
import gitlab
from cachelib import FileSystemCache
from flask import (
    Blueprint,
    Response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask import (
    current_app as flask_current_app,
)
from flask.typing import ResponseReturnValue
from pydantic import AnyUrl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession

from manytask import models

from . import abstract, course, database, glab, solutions
from .auth import requires_auth, requires_ready
from .config import ManytaskConfig, ManytaskDeadlinesConfig, ManytaskSettingsConfig, ManytaskUiConfig
from .course import Course, CourseConfig, get_current_time
from .database_utils import get_database_table_data
from .role import Role

SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint("web", __name__)


if TYPE_CHECKING:
    from flask import Flask

    class FlaskWithCourse(Flask):
        course: Course

    current_app: FlaskWithCourse
else:
    current_app = flask_current_app


def get_allscores_url(viewer_api: abstract.ViewerApi) -> str:
    """Function to get URL for viewing the scores

     :param viewer_api: The viewer API that may hold the URL

    :return: String with an URL
    """
    if viewer_api.get_scoreboard_url() == "":
        return url_for("web.show_database")
    else:
        return viewer_api.get_scoreboard_url()


@bp.route("/", methods=["GET", "POST"])
@requires_ready
@requires_auth
def course_page() -> ResponseReturnValue:
    course = get_course()
    storage_api = cast(database.DataBaseApi, course.storage_api)

    if current_app.debug:
        student_username = "guest"
        student_repo = course.gitlab_api.get_url_for_repo(student_username)
        student_role = Role.ADMIN if request.args.get("admin", None) in ("true", "1", "yes", None) else Role.STUDENT
    else:
        if not flask.session or "gitlab" not in flask.session:
            return redirect(url_for("web.logout"))

        try:
            student_username = flask.session["gitlab"]["username"]
            student_repo = flask.session["gitlab"]["repo"]
            student = course.gitlab_api.get_student(flask.session["gitlab"]["user_id"])
            stored_user = storage_api.get_stored_user(student)
            student_role = Role(stored_user.role.value)  # Convert from abstract.Role to role.Role
        except (KeyError, TypeError):
            return redirect(url_for("web.logout"))

    # update cache if more than 1h passed or in debug mode
    try:
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time
    except ValueError:
        cache_delta = timedelta(days=365)

    hours_in_seconds = 3600
    if course.debug or cache_delta.total_seconds() > hours_in_seconds:
        storage_api.update_cached_scores()
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time

    # get scores
    tasks_scores = storage_api.get_scores(student_username)
    tasks_stats = storage_api.get_stats()

    allscores_url = get_allscores_url(course.viewer_api)

    available_courses = []
    if isinstance(storage_api, database.DataBaseApi):
        with SQLAlchemySession(storage_api.engine) as session:
            courses = session.query(models.Course).all()
            available_courses = [{"name": c.name, "unique_course_name": c.unique_course_name} for c in courses]

    current_course_name = get_current_course_name()
    if current_course_name is None:
        current_course_name = ""

    return render_template(
        "tasks.html",
        task_base_url=course.gitlab_api.get_url_for_task_base(),
        username=student_username,
        course_name=course.config.settings.course_name if course.config else "",
        role=student_role,
        current_course=course,
        gitlab_url=course.gitlab_api.base_url,
        allscores_url=allscores_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        tasks_stats=tasks_stats,
        cache_delta=cache_delta,
        manytask_version=course.manytask_version,
        links=(course.config.ui.links if course.config else {}),
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(student_username),
        now=get_current_time(),
        task_stats=tasks_stats,
        course_favicon=course.favicon,
        is_course_admin=student_role == Role.ADMIN,
        cache_time=cache_time,
        current_course_name=current_course_name,
        available_courses=available_courses,
    )


@bp.get("/solutions")
@requires_auth
@requires_ready
def get_solutions() -> ResponseReturnValue:
    course = get_course()

    if current_app.debug:
        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student = course.gitlab_api.get_student(session["gitlab"]["user_id"])
        stored_user = course.storage_api.get_stored_user(student)

        student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

    if not student_course_admin:
        return "Possible only for admins", HTTPStatus.FORBIDDEN

    # ----- get and validate request parameters ----- #
    if "task" not in request.args:
        return "You didn't provide required param `task`", HTTPStatus.BAD_REQUEST
    task_name = request.args["task"]

    # TODO: parameter to return not aggregated solutions

    # ----- logic ----- #
    try:
        _, _ = course.deadlines.find_task(task_name)
    except KeyError:
        return f"There is no task with name `{task_name}` (or it is disabled)", HTTPStatus.NOT_FOUND

    zip_bytes_io = course.solutions_api.get_task_aggregated_zip_io(task_name)
    if not zip_bytes_io:
        return f"Unable to get zip for {task_name}", 500

    _now_str = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"aggregated-solutions-{task_name}-{_now_str}.zip"

    return Response(
        zip_bytes_io.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )


def get_course() -> Course:
    """Get the course from the current Flask app."""
    if not hasattr(current_app, "course"):
        raise RuntimeError("Course not initialized in Flask app")
    return current_app.course


@bp.route("/signup", methods=["GET", "POST"])
@requires_ready
def signup() -> ResponseReturnValue:
    course = get_course()

    target_course_name = request.args.get("course")
    if not target_course_name:
        target_course_name = course.name

    storage_api = course.storage_api
    logger.info(f"Target course name: {target_course_name}")
    target_course = storage_api.get_course_by_unique_name(target_course_name)
    if not target_course:
        return f"Course {target_course_name} not found", 404

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            course_name=target_course.name,
            course_favicon=course.favicon,
            manytask_version=course.manytask_version,
        )

    # ----  register a new user ---- #
    user = glab.User(
        username=request.form["username"].strip(),
        firstname=request.form["firstname"].strip(),
        lastname=request.form["lastname"].strip(),
        email=request.form["email"].strip(),
        password=request.form["password"],
    )

    try:
        existing_student = course.gitlab_api.get_student_by_username(user.username)
        if existing_student:
            if storage_api.check_user_on_course(target_course_name, existing_student):
                return redirect(url_for("web.login"))
            else:
                if not secrets.compare_digest(request.form["secret"], target_course.registration_secret):
                    raise Exception("Invalid registration secret")
                storage_api.sync_stored_user(existing_student, is_registration=True)
                return redirect(url_for("web.login"))

        if not secrets.compare_digest(request.form["secret"], target_course.registration_secret):
            raise Exception("Invalid registration secret")
        if not secrets.compare_digest(request.form["password"], request.form["password2"]):
            raise Exception("Passwords don't match")

        # register user in gitlab
        gitlab_user = course.gitlab_api.register_new_user(user)
        student = course.gitlab_api._parse_user_to_student(gitlab_user._attrs)
        # add user->course if not in db
        storage_api.sync_stored_user(student, is_registration=True)

    # render template with error... if error
    except Exception as e:
        logger.warning(f"User registration failed: {e}")
        return render_template(
            "signup.html",
            error_message=str(e),
            course_name=target_course.name,
            course_favicon=course.favicon,
            base_url=course.gitlab_api.base_url,
        )

    return redirect(url_for("web.login"))


@bp.route("/login", methods=["GET", "POST"])
@requires_ready
@requires_auth
def login() -> ResponseReturnValue:
    """Callback for gitlab oauth"""
    course = get_course()
    student = course.gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])

    if course.gitlab_api.check_project_exists(student):
        return redirect(url_for("web.course_page"))
    else:
        return redirect(url_for("web.create_project"))


@bp.route("/create_project", methods=["GET", "POST"])
@requires_ready
@requires_auth
def create_project() -> ResponseReturnValue:
    course = get_course()

    gitlab_access_token: str = session["gitlab"]["access_token"]
    student = course.gitlab_api.get_authenticated_student(gitlab_access_token)

    # Create use if needed
    try:
        course.gitlab_api.create_project(student)
    except gitlab.GitlabError as ex:
        logger.error(f"Project creation failed: {ex.error_message}")
        return render_template("signup.html", error_message=ex.error_message, course_name=course.name)

    return redirect(url_for("web.course_page"))


@bp.route("/logout")
def logout() -> ResponseReturnValue:
    session.pop("gitlab", None)
    return redirect(url_for("web.signup"))


@bp.route("/not_ready")
def not_ready() -> ResponseReturnValue:
    current_course_name = request.args.get("course") or get_current_course_name()

    course_name = ""
    error_message = request.args.get("error", "Course is not ready")

    database_url = os.environ.get("DATABASE_URL", "postgresql://adminmanytask:adminpass@postgres:5432/manytask")
    engine = create_engine(database_url)

    with SQLAlchemySession(engine) as session:
        if current_course_name:
            course_data = session.query(models.Course).filter_by(unique_course_name=current_course_name).first()
            if course_data:
                course_name = course_data.name

                task_groups = session.query(models.TaskGroup).filter_by(course_id=course_data.id).all()
                if not task_groups:
                    error_message = f"Course '{course_data.name}' has no task groups defined"
        else:
            first_course = session.query(models.Course).first()
            if first_course:
                course_name = first_course.name
            else:
                error_message = "No courses available in the system"

    if hasattr(current_app, "course") and current_app.course:
        manytask_version = current_app.course.manytask_version
    else:
        manytask_version = ""

    return render_template(
        "not_ready.html", manytask_version=manytask_version, course_name=course_name, error_message=error_message
    )


@bp.get("/database")
@requires_auth
@requires_ready
def show_database() -> ResponseReturnValue:
    course = get_course()
    storage_api = course.storage_api

    if current_app.debug:
        student_username = "guest"
        student_repo = course.gitlab_api.get_url_for_repo(student_username)

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
            student_role = Role.ADMIN
        else:
            student_course_admin = False
            student_role = Role.STUDENT
    else:
        student_username = session["gitlab"]["username"]
        student_repo = session["gitlab"]["repo"]

        student = course.gitlab_api.get_student(session["gitlab"]["user_id"])
        stored_user = storage_api.get_stored_user(student)

        student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin
        student_role = stored_user.role

    scores = storage_api.get_scores(student_username)
    bonus_score = storage_api.get_bonus_score(student_username)
    table_data = get_database_table_data()

    return render_template(
        "database.html",
        table_data=table_data,
        course_name=course.config.settings.course_name if course.config else "",
        scores=scores,
        bonus_score=bonus_score,
        username=student_username,
        is_course_admin=student_course_admin,
        role=student_role,
        current_course=course,
        course_favicon=course.favicon,
        readonly_fields=["username", "total_score"],  # Cannot be edited in database web viewer
        links=(course.config.ui.links if course.config else {}),
        gitlab_url=course.gitlab_api.base_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        current_course_name=get_current_course_name(),
    )


T = TypeVar("T", bound=Callable[..., Any])


def requires_admin(f: T) -> T:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if current_app.debug:
            return f(*args, **kwargs)

        stored_user = get_course().storage_api.get_stored_user(
            get_course().gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])
        )
        if stored_user.role != Role.ADMIN:
            return redirect(url_for("web.course_page"))

        return f(*args, **kwargs)

    return cast(T, decorated)


def requires_teacher_or_admin(f: T) -> T:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if current_app.debug:
            return f(*args, **kwargs)

        stored_user = get_course().storage_api.get_stored_user(
            get_course().gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])
        )
        if stored_user.role not in (Role.ADMIN, Role.TEACHER):
            return redirect(url_for("web.course_page"))

        return f(*args, **kwargs)

    return cast(T, decorated)


@bp.route("/admin/roles", methods=["GET"])
@requires_ready
@requires_auth
@requires_admin
def manage_roles() -> ResponseReturnValue:
    course = get_course()
    storage_api = course.storage_api

    student = course.gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])
    stored_user = storage_api.get_stored_user(student)
    student_username = student.username
    student_repo = student.repo or course.gitlab_api.get_url_for_repo(student_username)

    admins = course.storage_api.get_users_by_role(Role.ADMIN)
    teachers = course.storage_api.get_users_by_role(Role.TEACHER)
    students = course.storage_api.get_users_by_role(Role.STUDENT)

    tasks_scores = storage_api.get_scores(student_username)
    tasks_stats = storage_api.get_stats()

    return render_template(
        "manage_roles.html",
        admins=admins,
        teachers=teachers,
        students=students,
        username=student_username,
        course_name=course.config.settings.course_name if course.config else "",
        role=stored_user.role,
        current_course=course,
        gitlab_url=course.gitlab_api.base_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        tasks_stats=tasks_stats,
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(student_username),
        course_favicon=course.favicon,
        is_course_admin=stored_user.role == Role.ADMIN,
        links=(course.config.ui.links if course.config else {}),
    )


@bp.route("/admin/roles/<username>", methods=["POST"])
@requires_ready
@requires_auth
@requires_admin
def update_role(username: str) -> ResponseReturnValue:
    """Update user role"""
    course = get_course()
    role = request.form.get("role")

    if not role or role not in [r.value for r in Role]:
        return "Invalid request", 400

    current_username = session["gitlab"]["username"]
    if username == current_username and role != Role.ADMIN.value:
        return "You cannot remove your own admin role", 400

    try:
        course.storage_api.set_user_role(username, Role(role))
        return redirect(url_for("web.manage_roles"))
    except Exception as e:
        return str(e), 400


@bp.route("/admin/courses/new", methods=["GET", "POST"])
@requires_ready
@requires_auth
@requires_admin
def create_course() -> ResponseReturnValue:
    """Admin page for creating new courses"""
    course = get_course()
    storage_api = course.storage_api

    student = course.gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])
    stored_user = storage_api.get_stored_user(student)
    student_username = student.username
    student_repo = student.repo or course.gitlab_api.get_url_for_repo(student_username)
    tasks_scores = storage_api.get_scores(student_username)

    if request.method == "POST":
        try:
            settings = ManytaskSettingsConfig(
                course_name=request.form["course_name"],
                unique_course_name=request.form["unique_course_name"],
                gitlab_base_url=AnyUrl.build(scheme="https", host=request.form["gitlab_base_url"]),
                public_repo=request.form["public_repo"],
                students_group=request.form["students_group"],
                registration_secret=request.form["registration_secret"],
                token=request.form["token"],
                show_allscores=request.form["show_allscores"].lower() in ("true", "1", "yes"),
                gitlab_admin_token=request.form["gitlab_admin_token"],
                gitlab_course_group=request.form["gitlab_course_group"],
                gitlab_course_public_repo=request.form["gitlab_course_public_repo"],
                gitlab_course_students_group=request.form["gitlab_course_students_group"],
                gitlab_default_branch=request.form["gitlab_default_branch"],
                gitlab_client_id=request.form["gitlab_client_id"],
                gitlab_client_secret=request.form["gitlab_client_secret"],
            )

            ui = ManytaskUiConfig(
                task_url_template=f"https://{request.form['gitlab_base_url']}/test/$GROUP_NAME/$TASK_NAME", links={}
            )

            deadlines = ManytaskDeadlinesConfig(timezone="UTC", schedule=[])

            manytask_config = ManytaskConfig(version=1, settings=settings, ui=ui, deadlines=deadlines)
            storage_api.create_course(manytask_config)
            return redirect(url_for("web.course_page"))
        except Exception as e:
            error_message = str(e)
            return render_template(
                "create_course.html",
                error_message=error_message,
                username=student_username,
                course_name=course.config.settings.course_name if course.config else "",
                role=stored_user.role,
                current_course=course,
                gitlab_url=course.gitlab_api.base_url,
                show_allscores=course.show_allscores,
                student_repo_url=student_repo,
                student_ci_url=f"{student_repo}/pipelines",
                scores=tasks_scores,
                bonus_score=storage_api.get_bonus_score(student_username),
                course_favicon=course.favicon,
                is_course_admin=stored_user.role == Role.ADMIN,
                links=(course.config.ui.links if course.config else {}),
                active_page="create_course",
            )

    return render_template(
        "create_course.html",
        username=student_username,
        course_name=course.config.settings.course_name if course.config else "",
        role=stored_user.role,
        current_course=course,
        gitlab_url=course.gitlab_api.base_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(student_username),
        course_favicon=course.favicon,
        is_course_admin=stored_user.role == Role.ADMIN,
        links=(course.config.ui.links if course.config else {}),
        active_page="create_course",
    )


def get_current_course_name() -> str | None:
    return session.get("current_course")


def set_current_course(unique_course_name: str) -> None:
    session["current_course"] = unique_course_name


def get_default_course_config() -> CourseConfig:
    database_url = os.environ.get("DATABASE_URL", "postgresql://adminmanytask:adminpass@postgres:5432/manytask")
    db_config = database.DatabaseConfig(
        database_url=database_url,
        course_name="",  # Will be set after we find a valid course
        unique_course_name="",  # Will be set after we find a valid course
        gitlab_instance_host="",
        registration_secret="",
        token="",
        show_allscores=False,
        gitlab_admin_token="",
        gitlab_course_group="",
        gitlab_course_public_repo="",
        gitlab_course_students_group="",
        gitlab_default_branch="main",
        gitlab_client_id="",
        gitlab_client_secret="",
        gdoc_spreadsheet_id=None,
        gdoc_scoreboard_sheet=None,
        apply_migrations=False,
    )

    temp_storage_api = database.DataBaseApi(db_config)
    with SQLAlchemySession(temp_storage_api.engine) as session:
        first_course = session.query(models.Course).first()
        if first_course:
            logger.info(f"Found valid course: {first_course.name}")
            db_config.course_name = first_course.name
            db_config.unique_course_name = first_course.unique_course_name
            db_config.gitlab_instance_host = first_course.gitlab_instance_host
            db_config.registration_secret = first_course.registration_secret
            db_config.token = first_course.token
            db_config.show_allscores = first_course.show_allscores
            db_config.gitlab_admin_token = first_course.gitlab_admin_token
            db_config.gitlab_course_group = first_course.gitlab_course_group
            db_config.gitlab_course_public_repo = first_course.gitlab_course_public_repo
            db_config.gitlab_course_students_group = first_course.gitlab_course_students_group
            db_config.gitlab_default_branch = first_course.gitlab_default_branch
            db_config.gitlab_client_id = first_course.gitlab_client_id
            db_config.gitlab_client_secret = first_course.gitlab_client_secret
            db_config.gdoc_spreadsheet_id = first_course.gdoc_spreadsheet_id
            db_config.gdoc_scoreboard_sheet = first_course.gdoc_scoreboard_sheet

    storage_api = viewer_api = database.DataBaseApi(db_config)
    gitlab_api = glab.GitLabApi(
        glab.GitLabConfig(
            base_url=db_config.gitlab_instance_host,
            admin_token=db_config.gitlab_admin_token,
            course_group=db_config.gitlab_course_group,
            course_public_repo=db_config.gitlab_course_public_repo,
            course_students_group=db_config.gitlab_course_students_group,
            default_branch=db_config.gitlab_default_branch,
        )
    )
    solutions_api = solutions.SolutionsApi(base_folder=".tmp/solution")
    cache = FileSystemCache(".tmp/cache", threshold=0, default_timeout=0)
    course_config = CourseConfig(
        viewer_api=viewer_api,
        storage_api=storage_api,
        gitlab_api=gitlab_api,
        solutions_api=solutions_api,
        registration_secret=db_config.registration_secret,
        token=db_config.token,
        show_allscores=db_config.show_allscores,
        cache=cache,
        manytask_version="",
        debug=True,
    )
    return course_config


def _get_course_name_from_request() -> str:
    # Get course name from request args or session, defaulting to empty string
    current_course_name: str = request.args.get("course", "") or get_current_course_name() or ""

    temp_db_config = database.DatabaseConfig(
        database_url=os.environ.get("DATABASE_URL", "postgresql://adminmanytask:adminpass@postgres:5432/manytask"),
        course_name="",
        unique_course_name="",
        gitlab_instance_host="",
        registration_secret="",
        token="",
        show_allscores=False,
        gitlab_admin_token="",
        gitlab_course_group="",
        gitlab_course_public_repo="",
        gitlab_course_students_group="",
        gitlab_default_branch="main",
        gitlab_client_id="",
        gitlab_client_secret="",
        gdoc_spreadsheet_id=None,
        gdoc_scoreboard_sheet=None,
    )
    temp_storage_api = database.DataBaseApi(temp_db_config)

    with SQLAlchemySession(temp_storage_api.engine) as session:
        courses = session.query(models.Course).all()
        if not courses:
            flask.abort(redirect(url_for("web.not_ready")))

        if not current_course_name or not any(c.unique_course_name == current_course_name for c in courses):
            return courses[0].unique_course_name

        return current_course_name


def _create_course_config(course_data: models.Course) -> CourseConfig:
    db_config = database.DatabaseConfig(
        database_url=os.environ.get("DATABASE_URL", "postgresql://adminmanytask:adminpass@postgres:5432/manytask"),
        course_name=course_data.name,
        unique_course_name=course_data.unique_course_name,
        gitlab_instance_host=course_data.gitlab_instance_host,
        registration_secret=course_data.registration_secret,
        token=course_data.token,
        show_allscores=course_data.show_allscores,
        gitlab_admin_token=course_data.gitlab_admin_token,
        gitlab_course_group=course_data.gitlab_course_group,
        gitlab_course_public_repo=course_data.gitlab_course_public_repo,
        gitlab_course_students_group=course_data.gitlab_course_students_group,
        gitlab_default_branch=course_data.gitlab_default_branch,
        gitlab_client_id=course_data.gitlab_client_id,
        gitlab_client_secret=course_data.gitlab_client_secret,
        gdoc_spreadsheet_id=course_data.gdoc_spreadsheet_id,
        gdoc_scoreboard_sheet=course_data.gdoc_scoreboard_sheet,
    )

    storage_api = viewer_api = database.DataBaseApi(db_config)
    gitlab_api = glab.GitLabApi(
        glab.GitLabConfig(
            base_url=course_data.gitlab_instance_host,
            admin_token=course_data.gitlab_admin_token,
            course_group=course_data.gitlab_course_group,
            course_public_repo=course_data.gitlab_course_public_repo,
            course_students_group=course_data.gitlab_course_students_group,
            default_branch=course_data.gitlab_default_branch,
        )
    )
    solutions_api = solutions.SolutionsApi(base_folder=".tmp/solution")
    cache = FileSystemCache(".tmp/cache", threshold=0, default_timeout=0)

    return CourseConfig(
        viewer_api=viewer_api,
        storage_api=storage_api,
        gitlab_api=gitlab_api,
        solutions_api=solutions_api,
        registration_secret=course_data.registration_secret,
        token=course_data.token,
        show_allscores=course_data.show_allscores,
        cache=cache,
        manytask_version="",
        debug=True,
    )


def _build_task_configs(tasks: list[models.Task], group_start_time: datetime) -> tuple[list[dict[str, Any]], bool]:
    now = datetime.now(tz=ZoneInfo("UTC"))
    has_enabled_non_bonus_task = False
    task_configs: list[dict[str, Any]] = []

    for task in tasks:
        if not task.is_bonus and group_start_time <= now:
            has_enabled_non_bonus_task = True

        task_config = {
            "task": task.name,
            "enabled": group_start_time <= now,
            "is_bonus": task.is_bonus,
            "score": task.score,
            "is_special": task.is_special,
        }
        task_configs.append(task_config)

    return task_configs, has_enabled_non_bonus_task


def _build_group_config(group: models.TaskGroup, tasks: list[models.Task]) -> tuple[dict[str, Any], bool]:
    now = datetime.now(tz=ZoneInfo("UTC"))
    group_start_time = now

    if group.deadline and group.deadline.data:
        deadline_data = group.deadline.data
        if isinstance(deadline_data, dict):
            start_time = deadline_data.get("start", now.isoformat())
            group_start_time = datetime.fromisoformat(str(start_time))

    task_configs, has_enabled_non_bonus_task = _build_task_configs(tasks, group_start_time)

    group_config = {
        "group": group.name,
        "enabled": True,
        "tasks": task_configs,
        "special": group.is_special,
    }

    if group.deadline and group.deadline.data:
        deadline_data = group.deadline.data
        if isinstance(deadline_data, dict):
            current_time = datetime.now(tz=ZoneInfo("UTC"))
            start_time = deadline_data.get("start", current_time)
            end_time = deadline_data.get("end", current_time + timedelta(days=30))
            group_config["start"] = str(start_time)
            group_config["end"] = str(end_time)
            # Copy other fields except start and end
            for k, v in deadline_data.items():
                if k not in ["start", "end"]:
                    group_config[k] = v
    else:
        current_time = datetime.now(tz=ZoneInfo("UTC"))
        group_config["start"] = str(current_time)
        group_config["end"] = str(current_time + timedelta(days=30))

    return group_config, has_enabled_non_bonus_task


def _build_course_config(current_course: models.Course, schedule: list[dict[str, Any]]) -> dict[str, Any]:
    config = {
        "version": 1,
        "settings": {
            "course_name": current_course.name,
            "gitlab_base_url": current_course.gitlab_instance_host,
            "public_repo": current_course.gitlab_course_public_repo,
            "students_group": current_course.gitlab_course_students_group,
        },
        "ui": {
            "task_url_template": f"{current_course.gitlab_instance_host}/"
            f"{current_course.gitlab_course_group}/$GROUP_NAME/$TASK_NAME",
            "links": {},
        },
        "deadlines": {"timezone": "UTC", "schedule": schedule},
    }
    return config


def _should_skip_request(endpoint: str | None) -> bool:
    return not endpoint or endpoint.startswith("static") or endpoint == "web.not_ready"


def _load_course_schedule(
    storage_api: database.DataBaseApi, current_course_name: str
) -> tuple[models.Course, list[dict[str, Any]], bool]:
    if not isinstance(storage_api, database.DataBaseApi):
        raise TypeError("storage_api must be an instance of DataBaseApi")

    with SQLAlchemySession(storage_api.engine) as session:
        current_course = session.query(models.Course).filter_by(unique_course_name=current_course_name).first()
        if not current_course:
            flask.abort(redirect(url_for("web.not_ready")))

        task_groups = session.query(models.TaskGroup).filter_by(course_id=current_course.id).all()
        if not task_groups:
            flask.abort(redirect(url_for("web.not_ready")))

        has_enabled_non_bonus_tasks = False
        schedule = []

        for group in task_groups:
            tasks = session.query(models.Task).filter_by(group_id=group.id).all()
            if not tasks:
                continue

            group_config, has_enabled_task = _build_group_config(group, tasks)
            has_enabled_non_bonus_tasks = has_enabled_non_bonus_tasks or has_enabled_task
            schedule.append(group_config)

        if not schedule or not has_enabled_non_bonus_tasks:
            flask.abort(redirect(url_for("web.not_ready")))

        return current_course, schedule, has_enabled_non_bonus_tasks


@bp.before_request
def load_current_course() -> None:
    if _should_skip_request(request.endpoint):
        return

    current_course_name = get_current_course_name()
    if not current_course_name:
        return

    storage_api = get_course().storage_api
    if not isinstance(storage_api, database.DataBaseApi):
        return

    try:
        current_course, schedule, has_errors = _load_course_schedule(storage_api, current_course_name)
        course_config = _create_course_config(current_course)
        current_app.course = course.Course(course_config)
        config_data = _build_course_config(current_course, schedule)
        get_course().store_config(config_data)
    except Exception as e:
        logger.error(f"Failed to load course schedule: {e}")
        return


@bp.route("/courses/switch/<unique_course_name>", methods=["GET"])
@requires_ready
@requires_auth
def switch_course(unique_course_name: str) -> ResponseReturnValue:
    set_current_course(unique_course_name)
    return redirect(url_for("web.course_page"))


@bp.route("/courses/available", methods=["GET"])
@requires_ready
@requires_auth
def get_available_courses() -> ResponseReturnValue:
    course = get_course()
    storage_api = course.storage_api

    if not isinstance(storage_api, database.DataBaseApi):
        return flask.make_response(flask.jsonify({"courses": []}))

    with SQLAlchemySession(storage_api.engine) as session:
        courses = session.query(models.Course).all()
        available_courses = [
            {"name": course.name, "unique_course_name": course.unique_course_name} for course in courses
        ]

    return flask.make_response(flask.jsonify({"courses": available_courses}))


@bp.route("/courses/user", methods=["GET"])
@requires_ready
@requires_auth
def get_user_courses() -> ResponseReturnValue:
    course = get_course()
    storage_api = course.storage_api
    student_username = flask.session.get("gitlab", {}).get("username")

    if not student_username:
        return flask.make_response(flask.jsonify({"courses": []}))

    if not isinstance(storage_api, database.DataBaseApi):
        return flask.make_response(flask.jsonify({"courses": []}))

    with SQLAlchemySession(storage_api.engine) as session:
        user_courses = (
            session.query(models.Course)
            .join(models.UserOnCourse)
            .join(models.User)
            .filter(models.User.username == student_username)
            .all()
        )

        user_courses_list = [
            {"name": course.name, "unique_course_name": course.unique_course_name} for course in user_courses
        ]

    return flask.make_response(flask.jsonify({"courses": user_courses_list}))
