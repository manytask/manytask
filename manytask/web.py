import logging
import secrets
from datetime import datetime, timedelta

import gitlab
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue

from . import glab
from .auth import requires_auth, requires_ready, valid_session
from .course import Course, get_current_time
from .database_utils import get_database_table_data


SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint("web", __name__)

def get_allscores_url(viewer_api) -> str :
    if viewer_api.get_scoreboard_url() == None:
        return url_for('web.show_database')
    else:
        return viewer_api.get_scoreboard_url()

@bp.route("/")
def course_page() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    if not course.config:
        return redirect(url_for("web.not_ready"))

    if current_app.debug:
        student_username = "guest"
        student_repo = course.gitlab_api.get_url_for_repo(student_username)
        student_course_admin = True  # request.args.get('admin', None) is not None
    else:
        if not valid_session(session):
            return redirect(url_for("web.signup"))
        student_username = session["gitlab"]["username"]
        student_repo = session["gitlab"]["repo"]
        student_course_admin = session["gitlab"]["course_admin"]

    storage_api = course.storage_api

    # update cache if more than 1h passed or in debug mode
    try:
        cache_time = datetime.fromisoformat(str(storage_api.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time
    except ValueError:
        cache_delta = timedelta(days=365)
    if course.debug or cache_delta.total_seconds() > 3600:
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
        links=course.config.ui.links or dict(),
        scores=tasks_scores,
        bonus_score=storage_api.get_bonus_score(student_username),
        now=get_current_time(),
        task_stats=tasks_stats,
        course_favicon=course.favicon,
        is_course_admin=student_course_admin,
        cache_time=cache_delta,
    )


@bp.get("/solutions")
def get_solutions() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    if not course.config:
        return redirect(url_for("web.not_ready"))

    if current_app.debug:
        student_course_admin = True  # request.args.get('admin', None) is not None
    else:
        if not valid_session(session):
            return redirect(url_for("web.signup"))
        student_course_admin = session["gitlab"]["course_admin"]

    if not student_course_admin:
        return "Possible only for admins", 403

    # ----- get and validate request parameters ----- #
    if "task" not in request.args:
        return "You didn't provide required param `task`", 400
    task_name = request.args["task"]

    # TODO: parameter to return not aggregated solutions

    # ----- logic ----- #
    try:
        _, _ = course.deadlines.find_task(task_name)
    except KeyError:
        return f"There is no task with name `{task_name}` (or it is disabled)", 404

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
def signup() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    if not course.config and not current_app.debug:
        return redirect(url_for("web.not_ready"))

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            course_name=course.name,
            course_favicon=course.favicon,
            manytask_version=course.manytask_version,
        )

    # ----  register a new user ---- #
    # render template with error... if error
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
        _ = course.gitlab_api.register_new_user(user)
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


@bp.route("/login", methods=["GET"])
def login() -> ResponseReturnValue:
    """Only way to login - gitlab oauth"""
    course: Course = current_app.course  # type: ignore
    oauth: OAuth = current_app.oauth  # type: ignore

    if not course.config:
        return redirect(url_for("web.not_ready"))

    redirect_uri = url_for("web.login_finish", _external=True)

    return oauth.gitlab.authorize_redirect(redirect_uri)


@bp.route("/login_finish")
def login_finish() -> ResponseReturnValue:
    """Callback for gitlab oauth"""
    course: Course = current_app.course  # type: ignore
    oauth: OAuth = current_app.oauth  # type: ignore

    if not course.config:
        return redirect(url_for("web.not_ready"))

    # ----- oauth authorize ----- #
    try:
        gitlab_oauth_token = oauth.gitlab.authorize_access_token()
    except OAuthError:
        return redirect(url_for("web.login"))

    gitlab_access_token: str = gitlab_oauth_token["access_token"]
    gitlab_refresh_token: str = gitlab_oauth_token["refresh_token"]
    # gitlab_openid_user = oauth.gitlab.parse_id_token(
    #     gitlab_oauth_token,
    #     nonce='', claims_options={'iss': {'essential': False}}
    # )

    # get oauth student
    # TODO do not return 502 (raise_for_status below)
    student = course.gitlab_api.get_authenticated_student(gitlab_access_token)

    # save user in session
    session["gitlab"] = {
        "oauth_access_token": gitlab_access_token,
        "oauth_refresh_token": gitlab_refresh_token,
        "username": student.username,
        "user_id": student.id,
        "course_admin": student.course_admin,
        "repo": student.repo,
        "version": SESSION_VERSION,
    }
    session.permanent = True

    if (course.gitlab_api.check_project_exists(student)):
        return redirect(url_for("web.course_page"))
    else :
        return redirect(url_for("web.create_project"))

@bp.route("/create_project", methods=["GET", "POST"])
def create_project() -> ResponseReturnValue:
    course: Course = current_app.course  # type: ignore

    if not course.config and not current_app.debug:
        return redirect(url_for("web.not_ready"))
    
    if not valid_session(session):
        return redirect(url_for("web.signup"))

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "create_project.html",
            course_name=course.name,
            course_favicon=course.favicon,
            manytask_version=course.manytask_version,
        )

    if not secrets.compare_digest(request.form["secret"], course.registration_secret):
        logger.warning("Wrong registration secret when creating project")
        return render_template(
            "create_project.html",
            error_message="Wrong registration secret.",
            course_name=course.name,
            course_favicon=course.favicon,
            base_url=course.gitlab_api.base_url,
        )

    gitlab_access_token: str = session["gitlab"]["oauth_access_token"]
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
    return redirect(url_for("web.course_page"))


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
    
    if current_app.debug:
        student_username = "guest"
        student_course_admin = True
    else:
        student_username = session["gitlab"]["username"]
        student_course_admin = session["gitlab"]["course_admin"]

    storage_api = course.storage_api
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
        use_database_as_view=current_app.config.get('USE_DATABASE_AS_VIEW', False),
    )
