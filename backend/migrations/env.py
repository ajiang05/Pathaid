import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import Base
# Importing the models registers their tables on Base.metadata. Alembic uses
# that metadata when it compares the Python models with the database schema.
from app import models  # noqa: F401

# Alembic loads this object from alembic.ini.
config = context.config
# Configure Python logging only when the Alembic config defines loggers.
if config.config_file_name and config.get_section(config.config_ini_section).get("loggers"):
    fileConfig(config.config_file_name)
# Prefer the deployment's database URL. The SQLite default keeps local setup
# simple and matches the fallback used by the application.
config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", "sqlite:///./pathaid.db"))
target_metadata = Base.metadata


def run_migrations_offline():
    """Generate SQL without opening a live database connection."""
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Connect to the configured database and apply migrations directly."""
    # NullPool prevents the short-lived migration command from retaining
    # database connections after it finishes.
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# Alembic chooses the mode from the command being run.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


