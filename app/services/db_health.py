"""
Database connectivity utility.

This module answers one question: "is the configured database
reachable right now?" It does not define any models and does not
assume any schema exists yet - it only checks that a connection can be
opened and a trivial query executed.

Used by the /api/health/database endpoint, and safe to import and call
from anywhere else later (e.g. a future readiness probe) without
pulling in model code.
"""

from sqlalchemy import text

from app.extensions import db


def is_database_available() -> bool:
    """Return True if the configured database can be connected to.

    Runs a trivial `SELECT 1` through the existing SQLAlchemy engine.
    Any failure (missing driver, unreachable host, bad credentials,
    no DATABASE_URL configured, etc.) is treated as "unavailable" -
    the specific exception is never propagated or exposed to callers,
    so no internal stack trace or connection string ever reaches an
    API response.
    """
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
