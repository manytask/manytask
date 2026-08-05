from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import engine_from_config, pool

from manytask.models import Base

ENV_PATH = Path(__file__).parent.parent.parent / ".env"

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# if run from cli sqlalchemy.url is None
if config.get_main_option("sqlalchemy.url") is None:
    # is running from cli

    if config.config_file_name is not None:  # for logging
        fileConfig(config.config_file_name)

    dotenv_config = dotenv_values(ENV_PATH)

    database_url = dotenv_config.get("DATABASE_URL_EXTERNAL", "")

    if not database_url:
        database_url = dotenv_config.get("DATABASE_URL", None)

    if database_url is None:
        raise EnvironmentError("Unable to find DATABASE_URL and DATABASE_URL_EXTERNAL env")

    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
