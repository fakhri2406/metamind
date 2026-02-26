"""Alembic migration runner for MetaMind.

Wraps `alembic upgrade head` so the rest of the codebase can call
`run_migrations()` without knowing about Alembic internals.
"""

import os

from alembic import command
from alembic.config import Config

import config


def run_migrations() -> None:
    """Run all pending Alembic migrations (upgrade to head).

    Uses DATABASE_URL from config for the connection string.
    """
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = Config(alembic_ini)
    alembic_cfg.set_main_option("sqlalchemy.url", config.DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
