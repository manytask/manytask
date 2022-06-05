import base64
import json
import logging
import logging.handlers
import logging.config
import os
import secrets

from authlib.integrations.flask_client import OAuth
from cachelib import FileSystemCache
from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import course, deadlines, gdoc, glab


load_dotenv('../.env')  # take environment variables from .env.


def create_app(*, debug: bool = False, test: bool = False) -> Flask:
    app = Flask(__name__)

    # configuration
    # app.env = os.environ.get('FLASK_ENV', 'development')
    # app.debug = app.env == 'development'
    app.testing = os.environ.get('TESTING', test)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex())

    # oauth
    oauth = OAuth(app)
    _gitlab_base_url = os.environ['GITLAB_URL']
    oauth.register(
        name='gitlab',
        client_id=os.environ['GITLAB_CLIENT_ID'],
        client_secret=os.environ['GITLAB_CLIENT_SECRET'],
        authorize_url=f'{_gitlab_base_url}/oauth/authorize',
        access_token_url=f'{_gitlab_base_url}/oauth/token',
        userinfo_endpoint=f'{_gitlab_base_url}/oauth/userinfo',
        jwks_uri=f'{_gitlab_base_url}/oauth/discovery/keys',
        client_kwargs={'scope': 'openid email profile read_user', 'code_challenge_method': 'S256'},
    )
    app.oauth = oauth

    # logging
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            },
            'access': {
                'format': '%(message)s',
            }
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'stream': 'ext://sys.stdout',
            },
            'general_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'default',
                'filename': '/var/log/general.log',
                'maxBytes': 10 * 1000,
                'backupCount': 2,
                'delay': 'True',
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'default',
                'filename': '/var/log/error.log',
                'maxBytes': 10 * 1000,
                'backupCount': 2,
                'delay': 'True',
            },
            'access_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'access',
                'filename': '/var/log/access.log',
                'maxBytes': 10 * 1000,
                'backupCount': 2,
                'delay': 'True',
            }
        },
        'loggers': {
            'gunicorn.error': {
                'handlers': ['console'] if app.debug else ['console', 'error_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'gunicorn.access': {
                'handlers': ['console'] if app.debug else ['console', 'access_file'],
                'level': 'INFO',
                'propagate': False,
            }
        },
        'root': {
            'level': 'DEBUG' if app.debug else 'INFO',
            'handlers': ['console'] if app.debug else ['console', 'general_file'],
        },
    })

    # cache
    cache = FileSystemCache(
        os.environ['CACHE_DIR'],
        threshold=0,
        default_timeout=0
    )

    # api objects
    gitlab_api = glab.GitLabApi(
        base_url=os.environ['GITLAB_URL'],
        admin_token=os.environ['GITLAB_ADMIN_TOKEN'],
        course_public_repo=os.environ['GITLAB_COURSE_PUBLIC_REPO'],
        course_students_group=os.environ['GITLAB_COURSE_STUDENTS_GROUP'],
        course_admins_group=os.environ['GITLAB_COURSE_ADMINS_GROUP'],
    )
    _gdoc_credentials_string = base64.decodebytes(
        os.environ['GDOC_ACCOUNT_CREDENTIALS_BASE64'].encode()
    )
    gdoc_api = gdoc.GoogleDocAPI(
        base_url=os.environ['GDOC_URL'],
        gdoc_credentials=json.loads(_gdoc_credentials_string),
        public_worksheet_id=os.environ['GDOC_SPREADSHEET_ID'],
        public_scoreboard_sheet=int(os.environ['GDOC_SCOREBOARD_SHEET']),
        cache=cache,
    )
    deadlines_api = deadlines.DeadlinesAPI(
        cache=cache
    )

    # get additional info
    registration_secret = os.environ['REGISTRATION_SECRET']
    lms_url = os.environ.get('LMS_URL', 'https://lk.yandexdataschool.ru/')
    tg_invite_link = os.environ.get('TELEGRAM_INVITE_LINK', None)

    # create course
    _course = course.Course(
        deadlines_api, gdoc_api, gitlab_api, registration_secret, lms_url, tg_invite_link, debug=app.debug,
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
        app.course.deadlines_api.fetch_debug()

    logger.info('Init success')

    return app
