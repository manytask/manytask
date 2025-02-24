import base64
import json
import logging
import logging.config
import logging.handlers
import os
import secrets
from typing import Any

import yaml
from authlib.integrations.flask_client import OAuth
from cachelib import FileSystemCache
from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import abstract, config, course, database, gdoc, glab, local_config, solutions

load_dotenv("../.env")  # take environment variables from .env.


class CustomFlask(Flask):
    course: course.Course
    oauth: OAuth
    app_config: local_config.LocalConfig  # TODO: check if we need it


def create_app(*, debug: bool | None = None, test: bool = False) -> CustomFlask:
    app = CustomFlask(__name__)

    if debug:
        app.debug = debug

    _create_app_config(app, debug, test)

    # logging
    logging.config.dictConfig(_logging_config(app))

    # cache
    cache = FileSystemCache(app.app_config.cache_dir, threshold=0, default_timeout=0)

    # api objects
    gitlab_api = glab.GitLabApi(
        glab.GitLabConfig(
            base_url=app.app_config.gitlab_url,
            admin_token=app.app_config.gitlab_admin_token,
            course_group=app.app_config.gitlab_course_group,
            course_public_repo=app.app_config.gitlab_course_public_repo,
            course_students_group=app.app_config.gitlab_course_students_group,
            default_branch=app.app_config.gitlab_default_branch,
        )
    )

    storage_api: abstract.StorageApi
    viewer_api: abstract.ViewerApi
    storage = os.environ.get("STORAGE", "gsheets").lower()

    if storage == config.ManytaskStorageType.DataBase.value:
        storage_api, viewer_api = _database_storage_setup(app)
    elif storage == config.ManytaskStorageType.GoogleSheets.value:
        storage_api, viewer_api = _google_sheets_helper(cache)
    else:
        raise EnvironmentError(
            "STORAGE should be either '"
            + config.ManytaskStorageType.GoogleSheets.value
            + "' to store data in Google Sheets, or '"
            + config.ManytaskStorageType.DataBase.value
            + "' to use database. Set to '"
            + storage
            + "'."
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
        course.CourseConfig(
            viewer_api,
            storage_api,
            gitlab_api,
            solutions_api,
            app.app_config.registration_secret,
            app.app_config.course_token,
            app.app_config.show_allscores,
            cache,
            manytask_version=manytask_version,
            debug=app.debug,
        )
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


def _google_sheets_helper(cache: FileSystemCache) -> tuple[abstract.StorageApi, abstract.ViewerApi]:
    # google sheets (credentials base64 encoded json)
    gdoc_url = str(os.environ.get("GDOC_URL", "https://docs.google.com"))
    gdoc_account_credentials_base64 = os.environ.get("GDOC_ACCOUNT_CREDENTIALS_BASE64")
    # google public sheet
    gdoc_spreadsheet_id = str(os.environ["GDOC_SPREADSHEET_ID"])
    gdoc_scoreboard_sheet = int(os.environ.get("GDOC_SCOREBOARD_SHEET", 0))
    if gdoc_account_credentials_base64 is None:
        raise EnvironmentError("Unable to find GDOC_ACCOUNT_CREDENTIALS_BASE64 env")
    if gdoc_spreadsheet_id is None:
        raise EnvironmentError("Unable to find GDOC_SPREADSHEET_ID env")
    _gdoc_credentials_string = base64.decodebytes(str(gdoc_account_credentials_base64).encode())
    viewer_api = storage_api = gdoc.GoogleDocApi(
        gdoc.GDocConfig(
            base_url=gdoc_url,
            gdoc_credentials=json.loads(_gdoc_credentials_string),
            public_worksheet_id=gdoc_spreadsheet_id,
            public_scoreboard_sheet=gdoc_scoreboard_sheet,
            cache=cache,
        )
    )
    return storage_api, viewer_api


def _database_storage_setup(app: CustomFlask) -> tuple[abstract.StorageApi, abstract.ViewerApi]:
    database_url = os.environ.get("DATABASE_URL", None)
    course_name = os.environ.get("UNIQUE_COURSE_NAME", None)
    apply_migrations = os.environ.get("APPLY_MIGRATIONS", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    if database_url is None:
        raise EnvironmentError("Unable to find DATABASE_URL env")
    if course_name is None:
        raise EnvironmentError("Unable to find UNIQUE_COURSE_NAME env")
    viewer_api = storage_api = database.DataBaseApi(
        database.DatabaseConfig(
            database_url=database_url,
            course_name=course_name,
            gitlab_instance_host=app.app_config.gitlab_url,
            registration_secret=app.app_config.registration_secret,
            token=app.app_config.course_token,
            show_allscores=app.app_config.show_allscores,
            apply_migrations=apply_migrations,
        )
    )
    return storage_api, viewer_api


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
