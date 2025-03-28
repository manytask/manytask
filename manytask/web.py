import logging
import secrets
from datetime import datetime, timedelta
from http import HTTPStatus

import gitlab
from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue

from . import abstract, glab
from .auth import requires_auth, requires_ready
from .course import Course, get_current_time
from .database import TaskDisabledError
from .database_utils import get_database_table_data

SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint("web", __name__)


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
    course: Course = current_app.course  # type: ignore

    storage_api = course.storage_api

    if current_app.debug:
        student_username = "guest"
        student_repo = course.gitlab_api.get_url_for_repo(student_username)

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student_username = session["gitlab"]["username"]
        student_repo = session["gitlab"]["repo"]

        student = course.gitlab_api.get_student(session["gitlab"]["user_id"])
        stored_user = storage_api.get_stored_user(student)

        student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

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

    return render_template(
        "tasks.html",
        task_base_url=course.gitlab_api.get_url_for_task_base(),
        username=student_username,
        course_name=course.name,
        current_course=course,
        gitlab_url=course.gitlab_api.base_url,
        allscores_url=allscores_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        manytask_version=course.manytask_version,
        links=(course.config.ui.links if course.config else {}),
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(student_username),
        now=get_current_time(),
        task_stats=tasks_stats,
        course_favicon=course.favicon,
        is_course_admin=student_course_admin,
        cache_time=cache_delta,
    )


@bp.get("/solutions")
@requires_auth
@requires_ready
def get_solutions() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

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
        _, _ = course.storage_api.find_task(task_name)
    except (KeyError, TaskDisabledError):
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


@bp.route("/signup", methods=["GET", "POST"])
@requires_ready
def signup() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            course_name=course.name,
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
        if not secrets.compare_digest(request.form["secret"], course.registration_secret):
            raise Exception("Invalid registration secret")
        if not secrets.compare_digest(request.form["password"], request.form["password2"]):
            raise Exception("Passwords don't match")

        # register user in gitlab
        gitlab_user = course.gitlab_api.register_new_user(user)
        student = course.gitlab_api._parse_user_to_student(gitlab_user._attrs)
        # add user->course if not in db
        course.storage_api.sync_stored_user(student)

    # render template with error... if error
    except Exception as e:
        logger.warning(f"User registration failed: {e}")
        return render_template(
            "signup.html",
            error_message=str(e),
            course_name=course.name,
            course_favicon=course.favicon,
            base_url=course.gitlab_api.base_url,
        )

    return redirect(url_for("web.login"))


@bp.route("/login", methods=["GET", "POST"])
@requires_ready
@requires_auth
def login() -> ResponseReturnValue:
    """Callback for gitlab oauth"""
    course: Course = current_app.course  # type: ignore
    student = course.gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])

    if course.gitlab_api.check_project_exists(student):
        return redirect(url_for("web.course_page"))
    else:
        return redirect(url_for("web.create_project"))


@bp.route("/create_project", methods=["GET", "POST"])
@requires_ready
@requires_auth
def create_project() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

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
    course: Course = current_app.course  # type: ignore

    if course.config and not current_app.debug:
        return redirect(url_for("web.course_page"))

    return render_template(
        "not_ready.html",
        manytask_version=course.manytask_version,
    )


@bp.get("/database")
@requires_auth
@requires_ready
def show_database() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    storage_api = course.storage_api

    if current_app.debug:
        student_username = "guest"
        student_repo = course.gitlab_api.get_url_for_repo(student_username)

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student_username = session["gitlab"]["username"]
        student_repo = session["gitlab"]["repo"]

        student = course.gitlab_api.get_student(session["gitlab"]["user_id"])
        stored_user = storage_api.get_stored_user(student)

        student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

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
        current_course=course,
        course_favicon=course.favicon,
        readonly_fields=["username", "total_score"],  # Cannot be edited in database web viewer
        links=(course.config.ui.links if course.config else {}),
        gitlab_url=course.gitlab_api.base_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
    )
