import logging
import secrets
from datetime import datetime, timedelta

import flask.sessions
import gitlab
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue

from . import glab
from .course import Course, get_current_time


SESSION_VERSION = 1.5


logger = logging.getLogger(__name__)
bp = Blueprint("web", __name__)


def valid_session(user_session: flask.sessions.SessionMixin) -> bool:
    return (
        "gitlab" in user_session
        and "version" in user_session["gitlab"]
        and user_session["gitlab"]["version"] >= SESSION_VERSION
        and "username" in user_session["gitlab"]
        and "user_id" in user_session["gitlab"]
        and "repo" in user_session["gitlab"]
        and "course_admin" in user_session["gitlab"]
    )


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

    rating_table = course.rating_table

    # update cache if more than 1h passed or in debug mode
    try:
        cache_time = datetime.fromisoformat(str(rating_table.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time
    except ValueError:
        cache_delta = timedelta(days=365)
    if course.debug or cache_delta.total_seconds() > 3600:
        rating_table.update_cached_scores()
        cache_time = datetime.fromisoformat(str(rating_table.get_scores_update_timestamp()))
        cache_delta = datetime.now(tz=cache_time.tzinfo) - cache_time

    # get scores
    tasks_scores = rating_table.get_scores(student_username)
    tasks_stats = rating_table.get_stats()

    return render_template(
        "tasks.html",
        task_base_url=course.gitlab_api.get_url_for_task_base(),
        username=student_username,
        course_name=course.name,
        current_course=course,
        gitlab_url=course.gitlab_api.base_url,
        gdoc_url=course.googledoc_api.get_spreadsheet_url(),
        student_repo_url=student_repo,
        student_ci_url=f"{student_repo}/pipelines",
        manytask_version=course.manytask_version,
        links=course.config.ui.links or dict(),
        scores=tasks_scores,
        bonus_score=rating_table.get_bonus_score(student_username),
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

    use_whitelist = course.use_whitelist()

    # ---- render page ---- #
    if request.method == "GET":
        return render_template(
            "signup.html",
            use_whitelist=use_whitelist,
            course_name=course.name,
            course_favicon=course.favicon,
            manytask_version=course.manytask_version,
        )

    # ----  register a new user ---- #
    # render template with error... if error
    
    try:
    
        if use_whitelist:
    
            username = request.form["username"].strip()

            whitelisted = course.whitelist_table.get_whitelisted()

            if not username in whitelisted:
                raise Exception("User '" + username + "' is not in the whitelist")
        
            userdata = whitelisted.get(username)
            user = glab.User(
                username,
                userdata["firstname"],
                userdata["lastname"],
                userdata["email"],
                password=request.form["password"],
            )

        else:

            user = glab.User(
                username=request.form["username"].strip(),
                firstname=request.form["firstname"].strip(),
                lastname=request.form["lastname"].strip(),
                email=request.form["email"].strip(),
                password=request.form["password"],
            )
       
        _ = course.gitlab_api.register_new_user(user)

    except Exception as e:
        logger.warning(f"User registration failed: {e}")
        return render_template(
            "signup.html",
            error_message=str(e),
            use_whitelist=use_whitelist,
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

    # ----- get args ----- #
    is_create_project = True
    if "nocreate" in request.args:
        is_create_project = False
    if "not_create_project" in request.args:
        is_create_project = False

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

    # Create use if needed
    if is_create_project and not current_app.debug:
        try:
            course.gitlab_api.create_project(student)
        except gitlab.GitlabError as ex:
            logger.error(f"Project creation failed: {ex.error_message}")
            use_whitelist = course.use_whitelist()
            return render_template("signup.html",
                                   error_message=ex.error_message,
                                   use_whitelist=use_whitelist,
                                   course_name=course.name)

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
