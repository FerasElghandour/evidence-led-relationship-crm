"""Alembic environment, wired to the app's SQLAlchemy Base/engine.

V1 uses Base.metadata.create_all() for its one-command startup (see
src/database.py); this scaffold exists so future schema changes can be
migration-tracked with `alembic revision --autogenerate` instead of hand-edited.
"""
from __future__ import annotations

import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import ENGINE, Base  # noqa: E402
from src import models  # noqa: F401,E402  (register models on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(ENGINE.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with ENGINE.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
