"""Alembic environment for the local SQLite database."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import Settings
from app.database import Base, sqlite_url
from app import models  # noqa: F401


config = context.config
if config.config_file_name and config.get_section(config.config_ini_section).get("loggers"):
    fileConfig(config.config_file_name)
settings = Settings.from_env()
settings.prepare_directories()
config.set_main_option("sqlalchemy.url", sqlite_url(settings.database_path))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQLite migration SQL without opening the database."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations with foreign-key enforcement enabled."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        # SQLAlchemy 2 begins a transaction for the PRAGMA. Commit it before
        # Alembic opens the migration transaction so the version row persists.
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
