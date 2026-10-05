"""Alembic environment. DATABASE_URL comes from the environment/.env."""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import settings + models so autogenerate sees all tables.
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base  # noqa: E402
import app.models.models  # noqa: E402,F401

target_metadata = Base.metadata


def _db_url() -> str:
    return os.environ.get("DATABASE_URL") or get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(url=_db_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _db_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
