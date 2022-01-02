from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    from . import api, web

    app.register_blueprint(api.bp)
    app.register_blueprint(web.bp)

    return app
