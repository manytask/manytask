import logging
import os
import secrets

from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    # configuration
    # app.env = os.environ.get('FLASK_ENV', 'development')
    # app.debug = app.env == 'development'
    app.testing = os.environ.get('TESTING', False)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex())

    # logging
    if not app.debug:
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
    else:
        app.logger.setLevel(logging.DEBUG)

    # routes
    from . import api, web
    app.register_blueprint(api.bp)
    app.register_blueprint(web.bp)

    return app
