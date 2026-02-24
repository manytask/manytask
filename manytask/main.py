import logging
import logging.config
import logging.handlers
import os
import secrets
from typing import Any

import yaml
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from manytask.course import ManytaskDeadlinesType
from manytask.mock_auth import MockAuthApi
from manytask.mock_rms import MockRmsApi

from . import abstract, config, course, database, glab, local_config, sourcecraft, yandex_id
from .course import CourseStatus

MAX_AGE_IN_SECONDS = 86400

load_dotenv("../.env")  # take environment variables from .env.


class CustomFlask(Flask):
    csrf: CSRFProtect
    oauth: OAuth
    app_config: local_config.LocalConfig  # TODO: check if we need it
    rms_api: abstract.RmsApi
    auth_api: abstract.AuthApi
    storage_api: abstract.StorageApi

    manytask_version: str | None = None

    @property
    def favicon(self) -> str:
        return "favicon.ico"

    def store_config(self, course_name: str, content: dict[str, Any]) -> None:
        manytask_config = config.ManytaskConfig(**content)

        # Update course settings
        self.storage_api.update_course(course_name, manytask_config)


def create_app(*, debug: bool | None = None, test: bool = False) -> CustomFlask:
    app = CustomFlask(__name__)

    if debug:
        app.debug = debug

    _create_app_config(app, debug, test)

    # logging
    logging.config.dictConfig(_logging_config(app))

    # api objects
    app.storage_api = _database_storage_setup()

    rms = app.app_config.rms

    if rms == "gitlab":
        app.oauth = _authenticate(
            OAuth(app), app.app_config.gitlab_url, app.app_config.gitlab_client_id, app.app_config.gitlab_client_secret
        )
        gitlab_api: glab.GitLabApi = glab.GitLabApi(
            glab.GitLabConfig(
                base_url=app.app_config.gitlab_url,
                admin_token=app.app_config.gitlab_admin_token,
                verify_ssl=app.app_config.gitlab_verify_ssl,
            )
        )
        app.auth_api = gitlab_api
        app.rms_api = gitlab_api

    elif rms == "sourcecraft":
        app.oauth = _create_yandex_id_oauth(
            OAuth(app),
            app.app_config.yandex_id_client_id,
            app.app_config.yandex_id_client_secret,
        )
        app.auth_api = yandex_id.YandexIDApi(yandex_id.YandexIDConfig())
        app.rms_api = sourcecraft.SourceCraftApi(
            sourcecraft.SourceCraftConfig(
                base_url=app.app_config.sourcecraft_url,
                api_url=app.app_config.sourcecraft_api_url,
                admin_token=app.app_config.sourcecraft_admin_token,
                org_slug=app.app_config.sourcecraft_org_slug,
            ),
            app.storage_api,
        )

    elif rms == "mock":
        app.oauth = _authenticate(
            OAuth(app), app.app_config.gitlab_url, app.app_config.gitlab_client_id, app.app_config.gitlab_client_secret
        )
        app.auth_api = MockAuthApi()
        app.rms_api = MockRmsApi(base_url=app.app_config.gitlab_url)

    app.csrf = CSRFProtect(app)

    # read VERSION file to get a version
    app.manytask_version = ""
    try:
        with open("VERSION", "r") as f:
            app.manytask_version = f.read().strip()
    except FileNotFoundError:
        pass

    # for https support
    _wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    app.wsgi_app = _wsgi_app  # type: ignore

    # routes
    from . import api, web

    app.register_blueprint(api.bp)
    app.csrf.exempt(api.bp)
    app.register_blueprint(api.namespace_bp)
    app.csrf.exempt(api.namespace_bp)
    app.register_blueprint(web.root_bp)
    app.register_blueprint(web.course_bp)
    app.register_blueprint(web.instance_admin_bp)

    from .utils.flask import get_user_roles, has_role

    app.jinja_env.globals["get_user_roles"] = get_user_roles
    app.jinja_env.globals["has_role"] = has_role

    logger = logging.getLogger(__name__)

    # debug updates
    if app.debug:
        _create_debug_course(app)

        with open(".manytask.example.yml", "r") as f:
            debug_manytask_config_data = yaml.load(f, Loader=yaml.SafeLoader)
        app.store_config("python2025", debug_manytask_config_data)

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = MAX_AGE_IN_SECONDS

    logger.info("Init success")

    return app


def _create_debug_course(app: CustomFlask) -> None:
    course_config = course.CourseConfig(
        course_name="python2025",
        namespace_id=None,
        gitlab_course_group="",
        gitlab_course_public_repo="",
        gitlab_course_students_group="",
        gitlab_default_branch="main",
        registration_secret="registration_secret",
        token="token",
        show_allscores=True,
        status=CourseStatus.CREATED,
        task_url_template="",
        links={},
        deadlines_type=ManytaskDeadlinesType.HARD,
    )
    app.storage_api.create_course(course_config)


def _database_storage_setup() -> abstract.StorageApi:
    database_url = os.environ.get("DATABASE_URL", None)
    apply_migrations = os.environ.get("APPLY_MIGRATIONS", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    if database_url is None:
        raise EnvironmentError("Unable to find DATABASE_URL env")

    instance_admin_username = os.environ.get("INITIAL_INSTANCE_ADMIN", None)

    if instance_admin_username is None:
        raise EnvironmentError("Unable to find INITIAL_INSTANCE_ADMIN env")

    if app.debug:
        rms_user = abstract.RmsUser(id=-1, username="username", name="First Last")
    else:
        rms_user = app.rms_api.get_rms_user_by_username(instance_admin_username)

    storage_api = database.DataBaseApi(
        database.DatabaseConfig(
            database_url=database_url,
            instance_admin_username=instance_admin_username,
            instance_admin_rms_id=rms_user.id,
            apply_migrations=apply_migrations,
        )
    )
    return storage_api


def _logging_config(app: CustomFlask) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] [%(levelname)s] - "
                "[process-%(process)d:%(thread)d] app in [%(module)s:%(lineno)s] : %(message)s",
            },
            "access": {
                "format": "[%(asctime)s] - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG" if app.debug else "INFO",
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "general_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": "/var/log/general.log",
                "maxBytes": 10 * 1000,
                "backupCount": 2,
                "delay": "True",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": "/var/log/error.log",
                "maxBytes": 10 * 1000,
                "backupCount": 2,
                "delay": "True",
            },
            "access_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "access",
                "filename": "/var/log/access.log",
                "maxBytes": 10 * 1000,
                "backupCount": 2,
                "delay": "True",
            },
        },
        "loggers": {
            "gunicorn.error": {
                "handlers": ["console"] if app.debug else ["console", "error_file"],
                "level": "INFO",
                "propagate": False,
            },
            "gunicorn.access": {
                "handlers": (["console"] if app.debug else ["console", "access_file"]),
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "level": "DEBUG" if app.debug else "INFO",
            "handlers": ["console"] if app.debug else ["console", "general_file"],
        },
    }


def _create_app_config(app: CustomFlask, debug: bool | None, test: bool) -> None:
    # configuration
    if app.debug:
        app.app_config = local_config.DebugLocalConfig.from_env()
    elif test:
        app.app_config = local_config.TestConfig()
    else:
        app.app_config = local_config.LocalConfig.from_env()  # read config from env
    app.testing = os.environ.get("TESTING", test)
    if "FLASK_SECRET_KEY" not in os.environ and not debug:
        raise EnvironmentError("Unable to find FLASK_SECRET_KEY env in production mode")
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex())


def _authenticate(oauth: OAuth, base_url: str, client_id: str, client_secret: str) -> OAuth:
    client_kwargs = {
        "scope": "openid email profile read_user",
        "code_challenge_method": "S256",
    }

    oauth.register(
        name="gitlab",
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=f"{base_url}/oauth/authorize",
        access_token_url=f"{base_url}/oauth/token",
        userinfo_endpoint=f"{base_url}/oauth/userinfo",
        jwks_uri=f"{base_url}/oauth/discovery/keys",
        client_kwargs=client_kwargs,
    )
    return oauth


def _create_yandex_id_oauth(oauth: OAuth, client_id: str, client_secret: str) -> OAuth:
    oauth.register(
        name="gitlab",  # TODO: rename to yandex_id and switch based on config OR register as "remote_app"
        client_id=client_id,
        client_secret=client_secret,
        access_token_url="https://oauth.yandex.com/token",
        authorize_url="https://oauth.yandex.com/authorize",
        api_base_url="https://login.yandex.ru/info",
        client_kwargs={"scope": "login:info"},
    )
    return oauth
