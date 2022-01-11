import pytest
from flask import Flask
from flask.testing import FlaskClient

from manytask.main import create_app


@pytest.fixture()
def flask_test_app() -> FlaskClient:
    app = create_app(test=True)
    yield app


@pytest.fixture()
def flask_test_client(flask_test_app: Flask) -> FlaskClient:
    with flask_test_app.test_client() as client:
        yield client
