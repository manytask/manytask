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
from werkzeug.middleware.proxy_fix import ProxyFix

from . import abstract, config, course, database, glab, local_config

load_dotenv("../.env")  # take environment variables from .env.


class CustomFlask(Flask):
    oauth: OAuth
    app_config: local_config.LocalConfig  # TODO: check if we need it
    gitlab_api: glab.GitLabApi
    rms_api: abstract.RmsApi
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
    gitlab_api: glab.GitLabApi = glab.GitLabApi(
        glab.GitLabConfig(
            base_url=app.app_config.gitlab_url,
            admin_token=app.app_config.gitlab_admin_token,
        )
    )

    app.gitlab_api = gitlab_api
    app.rms_api = gitlab_api

    # read VERSION file to get a version
    app.manytask_version = ""
    try:
        with open("VERSION", "r") as f:
            app.manytask_version = f.read().strip()
    except FileNotFoundError:
        pass

    app.storage_api = _database_storage_setup(app)

    # for https support
    _wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    app.wsgi_app = _wsgi_app  # type: ignore

    # routes
    from . import api, web

    app.register_blueprint(api.bp)
    app.register_blueprint(web.root_bp)
    app.register_blueprint(web.course_bp)
    app.register_blueprint(web.admin_bp)

    logger = logging.getLogger(__name__)

    # debug updates
    if app.debug:
        _create_debug_course(app)

        with open(".manytask.example.yml", "r") as f:
            debug_manytask_config_data = yaml.load(f, Loader=yaml.SafeLoader)
        app.store_config("python2025", debug_manytask_config_data)

    logger.info("Init success")

    return app


def _create_debug_course(app: CustomFlask) -> None:
    course_config = course.CourseConfig(
        course_name="python2025",
        gitlab_course_group="",
        gitlab_course_public_repo="",
        gitlab_course_students_group="",
        gitlab_default_branch="main",
        registration_secret="registration_secret",
        token="token",
        show_allscores=True,
        is_ready=False,
        task_url_template="",
        links={},
    )
    app.storage_api.create_course(course_config)


def _database_storage_setup(app: CustomFlask) -> abstract.StorageApi:
    database_url = os.environ.get("DATABASE_URL", None)
    apply_migrations = os.environ.get("APPLY_MIGRATIONS", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    if database_url is None:
        raise EnvironmentError("Unable to find DATABASE_URL env")
    storage_api = database.DataBaseApi(
        database.DatabaseConfig(
            database_url=database_url,
            gitlab_instance_host=app.app_config.gitlab_url,
            apply_migrations=apply_migrations,
        )
    )
    return storage_api


def _logging_config(app: CustomFlask) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s - "
                "process-%(process)d:%(thread)d app in %(filename)s : %(message)s",
            },
            "access": {
                "format": "%(message)s",
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
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

    # oauth
    oauth = OAuth(app)
    _gitlab_base_url = app.app_config.gitlab_url
    oauth.register(
        name="gitlab",
        client_id=app.app_config.gitlab_client_id,
        client_secret=app.app_config.gitlab_client_secret,
        authorize_url=f"{_gitlab_base_url}/oauth/authorize",
        access_token_url=f"{_gitlab_base_url}/oauth/token",
        userinfo_endpoint=f"{_gitlab_base_url}/oauth/userinfo",
        jwks_uri=f"{_gitlab_base_url}/oauth/discovery/keys",
        client_kwargs={
            "scope": "openid email profile read_user",
            "code_challenge_method": "S256",
        },
    )
    app.oauth = oauth
