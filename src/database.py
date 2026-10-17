"""Database engine, session factory, and one-command initialization.

Version 1 uses SQLAlchemy ``create_all`` for a reliable one-command startup.
Alembic scaffolding is included under ``migrations/`` for future schema
versioning; see README.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=os.getenv("ICP_CRM_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("icp_crm")


def _database_url() -> str:
    url = os.getenv("ICP_CRM_DATABASE_URL", "sqlite:///database/icp_crm.db")
    # Resolve a relative sqlite path against the project root so the app can be
    # launched from anywhere.
    prefix = "sqlite:///"
    if url.startswith(prefix):
        raw = url[len(prefix):]
        p = Path(raw)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{p}"
    return url


class Base(DeclarativeBase):
    pass


ENGINE = create_engine(_database_url(), echo=False, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session scope. Commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """Return a raw session (caller is responsible for closing/committing)."""
    return SessionLocal()


def init_db(seed: bool | None = None) -> None:
    """Create all tables and optionally seed reference + research data."""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(ENGINE)
    logger.info("Database schema ensured at %s", ENGINE.url)

    if seed is None:
        seed = os.getenv("ICP_CRM_SEED_ON_INIT", "0") == "1"
    if seed:
        from .imports import seed_initial_data

        created = seed_initial_data()
        if created:
            logger.info("Seeded initial research data (%s companies).", created)
        else:
            logger.info("Seed skipped (data already present).")
