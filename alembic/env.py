"""Alembic environment configuration for MetaMind."""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure project root is on sys.path so we can import config, models, etc.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config as app_config  # noqa: E402
from storage.base import Base  # noqa: E402

# Import all models so they register on Base.metadata
from storage.accounts import Account  # noqa: E402, F401
from storage.logger import RunLog  # noqa: E402, F401

# Alembic Config object
alembic_cfg = context.config

# Set the database URL from our app config (overrides alembic.ini placeholder)
if app_config.DATABASE_URL:
    alembic_cfg.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)

# Python logging
if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        alembic_cfg.get_section(alembic_cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
