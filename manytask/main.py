import base64
import json
import logging
import logging.config
import logging.handlers
import os
import secrets

import yaml
from authlib.integrations.flask_client import OAuth
from cachelib import FileSystemCache
from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import course, gdoc, glab, local_config, solutions


load_dotenv("../.env")  # take environment variables from .env.


class CustomFlask(Flask):
    course: course.Course
    oauth: OAuth
    app_config: local_config.LocalConfig  # TODO: check if we need it


def create_app(*, debug: bool | None = None, test: bool = False) -> CustomFlask:
    app = CustomFlask(__name__)

    if debug:
        app.debug = debug

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

    # logging
    logging.config.dictConfig(
        {
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
    )

    # cache
    cache = FileSystemCache(app.app_config.cache_dir, threshold=0, default_timeout=0)

    # api objects
    gitlab_api = glab.GitLabApi(
        base_url=app.app_config.gitlab_url,
        admin_token=app.app_config.gitlab_admin_token,
        course_group=app.app_config.gitlab_course_group,
        course_public_repo=app.app_config.gitlab_course_public_repo,
        course_students_group=app.app_config.gitlab_course_students_group,
        default_branch=app.app_config.gitlab_default_branch,
    )
    _gdoc_credentials_string = base64.decodebytes(app.app_config.gdoc_account_credentials_base64.encode())
    gdoc_api = gdoc.GoogleDocApi(
        base_url=app.app_config.gdoc_url,
        gdoc_credentials=json.loads(_gdoc_credentials_string),
        public_worksheet_id=app.app_config.gdoc_spreadsheet_id,
        public_scoreboard_sheet=int(app.app_config.gdoc_scoreboard_sheet),
        public_whitelist_id=app.app_config.gdoc_whitelist_id,
        public_whitelist_sheet=int(app.app_config.gdoc_whitelist_sheet),
        cache=cache,
    )
    solutions_api = solutions.SolutionsApi(
        base_folder=(".tmp/solution" if app.debug else os.environ.get("SOLUTIONS_DIR", "/solutions")),
    )

    # read VERSION file to get a version
    manytask_version = ""
    try:
        with open("VERSION", "r") as f:
            manytask_version = f.read().strip()
    except FileNotFoundError:
        pass

    # create course
    _course = course.Course(
        gdoc_api,
        gitlab_api,
        solutions_api,
        app.app_config.registration_secret,
        cache,
        manytask_version=manytask_version,
        debug=app.debug,
    )
    app.course = _course

    # for https support
    _wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    app.wsgi_app = _wsgi_app  # type: ignore

    # routes
    from . import api, web

    app.register_blueprint(api.bp)
    app.register_blueprint(web.bp)

    logger = logging.getLogger(__name__)

    # debug updates
    if app.course.debug:
        with open(".manytask.example.yml", "r") as f:
            debug_manytask_config_data = yaml.load(f, Loader=yaml.SafeLoader)
        app.course.store_config(debug_manytask_config_data)

    logger.info("Init success")

    return app
