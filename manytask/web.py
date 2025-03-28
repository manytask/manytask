import logging
import secrets
from datetime import datetime, timedelta

import gitlab
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import HTTPException

from . import abstract, glab
from .auth import requires_auth
from .course import Course, get_current_time
from .database_utils import get_database_table_data
from .utils import get_current_course

SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint("web", __name__)


@bp.route("/", methods=["GET", "POST"])
@requires_auth
def course_page() -> ResponseReturnValue:
    course: Course = get_current_course(request.cookies)

    storage_api = current_app.storage_api

    if current_app.debug:
        student_username = "guest"
        student_repo = current_app.gitlab_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student_username = session["gitlab"]["username"]
        student_repo = session["gitlab"]["repo"]

        student = course.gitlab_api.get_student(
            user_id=session["gitlab"]["user_id"],
            course_group=course.gitlab_course_group,
            course_students_group=course.gitlab_course_students_group,
        )
        student = course.gitlab_api.get_student(
            user_id=session["gitlab"]["user_id"],
            course_group=course.gitlab_course_group,
            course_students_group=course.gitlab_course_students_group,
        )
        stored_user = storage_api.get_stored_user(student)

        student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

    # update cache if more than 1h passed or in debug mode
    try:
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time
    except ValueError:
        cache_delta = timedelta(days=365)

    hours_in_seconds = 3600
    if current_app.debug or cache_delta.total_seconds() > hours_in_seconds:
        storage_api.update_cached_scores()
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time

    # get scores
    tasks_scores = storage_api.get_scores(student_username)
    tasks_stats = storage_api.get_stats()

    allscores_url = url_for("web.show_database")

    return render_template(
        "tasks.html",
        task_base_url=current_app.gitlab_api.get_url_for_task_base(
            course.gitlab_course_public_repo, course.gitlab_default_branch
        ),
        username=student_username,
        course_name=course.course_name,
        current_course=course,
        gitlab_url=current_app.gitlab_api.base_url,
        allscores_url=allscores_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        manytask_version=current_app.manytask_version,
        links=course.links,
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(student_username),
        now=get_current_time(),
        task_stats=tasks_stats,
        course_favicon=current_app.favicon,
        is_course_admin=student_course_admin,
        cache_time=cache_delta,
    )


# @bp.get("/solutions")
# @requires_auth
# def get_solutions() -> ResponseReturnValue:
#     course: Course = current_app.course  # type: ignore

#     if current_app.debug:
#         if request.args.get("admin", None) in ("true", "1", "yes", None):
#             student_course_admin = True
#         else:
#             student_course_admin = False
#     else:
#         student = course.gitlab_api.get_student(
#             session["gitlab"]["user_id"], course.gitlab_course_group, course.gitlab_course_students_group
#         )
#         stored_user = course.storage_api.get_stored_user(student)

#         student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

#     if not student_course_admin:
#         return "Possible only for admins", HTTPStatus.FORBIDDEN

#     # ----- get and validate request parameters ----- #
#     if "task" not in request.args:
#         return "You didn't provide required param `task`", HTTPStatus.BAD_REQUEST
#     task_name = request.args["task"]

#     # TODO: parameter to return not aggregated solutions

#     # ----- logic ----- #
#     try:
#         _, _ = course.storage_api.find_task(task_name)
#     except (KeyError, TaskDisabledError):
#         return f"There is no task with name `{task_name}` (or it is disabled)", HTTPStatus.NOT_FOUND

#     zip_bytes_io = course.solutions_api.get_task_aggregated_zip_io(task_name)
#     if not zip_bytes_io:
#         return f"Unable to get zip for {task_name}", 500

#     _now_str = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
#     filename = f"aggregated-solutions-{task_name}-{_now_str}.zip"

#     return Response(
#         zip_bytes_io.getvalue(),
#         mimetype="application/zip",
#         headers={"Content-Disposition": f"attachment;filename={filename}"},
#     )


@bp.route("/signup", methods=["GET", "POST"])
def signup() -> ResponseReturnValue:
    course: Course = get_current_course(request.cookies)

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            course_name=course.course_name,
            course_favicon=current_app.favicon,
            manytask_version=current_app.manytask_version,
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
        gitlab_user = current_app.gitlab_api.register_new_user(user)
        student = current_app.gitlab_api._parse_user_to_student(
            gitlab_user._attrs, course.gitlab_course_group, course.gitlab_course_students_group
        )
        # add user->course if not in db
        current_app.storage_api.sync_stored_user(student)

    # render template with error... if error
    except Exception as e:
        logger.warning(f"User registration failed: {e}")
        return render_template(
            "signup.html",
            error_message=str(e),
            course_name=course.course_name,
            course_favicon=current_app.favicon,
            base_url=current_app.gitlab_api.base_url,
        )

    return redirect(url_for("web.login"))


@bp.route("/login", methods=["GET", "POST"])
@requires_auth
def login() -> ResponseReturnValue:
    """Callback for gitlab oauth"""
    course: Course = get_current_course(request.cookies)
    student = current_app.gitlab_api.get_authenticated_student(
        session["gitlab"]["access_token"], course.gitlab_course_group, course.gitlab_course_students_group
    )

    if current_app.gitlab_api.check_project_exists(
        student=student, course_students_group=course.gitlab_course_students_group
    ):
        return redirect(url_for("web.course_page"))
    else:
        return redirect(url_for("web.create_project"))


@bp.route("/create_project", methods=["GET", "POST"])
@requires_auth
def create_project() -> ResponseReturnValue:
    course: Course = get_current_course(request.cookies)

    gitlab_access_token: str = session["gitlab"]["access_token"]
    student = current_app.gitlab_api.get_authenticated_student(
        gitlab_access_token, course.gitlab_course_group, course.gitlab_course_students_group
    )

    # Create use if needed
    try:
        current_app.gitlab_api.create_project(
            student, course.gitlab_course_students_group, course.gitlab_course_public_repo
        )
    except gitlab.GitlabError as ex:
        logger.error(f"Project creation failed: {ex.error_message}")
        return render_template("signup.html", error_message=ex.error_message, course_name=course.course_name)

    return redirect(url_for("web.course_page"))


@bp.route("/logout")
def logout() -> ResponseReturnValue:
    session.pop("gitlab", None)
    return redirect(url_for("web.signup"))


@bp.route("/not_ready")
def not_ready() -> ResponseReturnValue:
    try:
        get_current_course(request.cookies)
    except HTTPException:
        return render_template(
            "not_ready.html",
            manytask_version=current_app.manytask_version,
        )

    return redirect(url_for("web.course_page"))


@bp.get("/database")
@requires_auth
def show_database() -> ResponseReturnValue:
    course: Course = get_current_course(request.cookies)

    storage_api = current_app.storage_api

    if current_app.debug:
        student_username = "guest"
        student_repo = current_app.gitlab_api.get_url_for_repo(
            username=student_username, course_students_group=course.gitlab_course_students_group
        )

        if request.args.get("admin", None) in ("true", "1", "yes", None):
            student_course_admin = True
        else:
            student_course_admin = False
    else:
        student_username = session["gitlab"]["username"]
        student_repo = session["gitlab"]["repo"]

        student = current_app.gitlab_api.get_student(
            session["gitlab"]["user_id"], course.gitlab_course_group, course.gitlab_course_students_group
        )
        stored_user = storage_api.get_stored_user(student)

        student_course_admin = session["gitlab"]["course_admin"] or stored_user.course_admin

    scores = storage_api.get_scores(student_username)
    bonus_score = storage_api.get_bonus_score(student_username)
    table_data = get_database_table_data()

    return render_template(
        "database.html",
        table_data=table_data,
        course_name=course.course_name,
        scores=scores,
        bonus_score=bonus_score,
        username=student_username,
        is_course_admin=student_course_admin,
        current_course=course,
        course_favicon=current_app.favicon,
        readonly_fields=["username", "total_score"],  # Cannot be edited in database web viewer
        links=course.links,
        gitlab_url=current_app.gitlab_api.base_url,
        show_allscores=course.show_allscores,
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
    )
