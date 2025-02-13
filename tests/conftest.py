import time

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from manytask.main import create_app

ALEMBIC_PATH = "manytask/alembic.ini"


@pytest.fixture()
def flask_test_app() -> FlaskClient:
    app = create_app(test=True)
    yield app


@pytest.fixture()
def flask_test_client(flask_test_app: Flask) -> FlaskClient:
    with flask_test_app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def postgres_container():
    postgres = PostgresContainer("postgres:17")

    postgres.start()

    # Wait for PostgreSQL to be ready
    max_retries = 30
    retry_interval = 1
    for _ in range(max_retries):
        try:
            engine = create_engine(postgres.get_connection_url())
            with engine.connect() as connection:
                connection.execute(text("DROP SCHEMA public CASCADE"))
                connection.execute(text("CREATE SCHEMA public"))
                connection.execute(text("SELECT 1"))
                break
        except Exception:
            time.sleep(retry_interval)
    else:
        raise Exception("PostgreSQL container not ready after maximum retries")

    try:
        yield postgres
    finally:
        postgres.stop()


@pytest.fixture
def engine(postgres_container):
    return create_engine(postgres_container.get_connection_url(), echo=False)


@pytest.fixture
def alembic_cfg(postgres_container):
    return Config(ALEMBIC_PATH, config_args={"sqlalchemy.url": postgres_container.get_connection_url()})


@pytest.fixture
def tables(engine, alembic_cfg):
    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.downgrade(alembic_cfg, "base")  # Base.metadata.drop_all(engine)
        command.upgrade(alembic_cfg, "head")  # Base.metadata.create_all(engine)

    yield

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.downgrade(alembic_cfg, "base")  # Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    with Session(engine) as session:
        yield session
