from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.config import settings

DB_PATH = settings.database_url.replace("sqlite:///", "")


def _get_db_path() -> Path:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db() -> None:
    """Initialize the database with WAL mode and execute schema."""
    db_path = _get_db_path()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA wal_autocheckpoint = 1000;")

        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            conn.executescript(schema_path.read_text(encoding="utf-8"))

        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection with WAL pragmas applied."""
    db_path = _get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_transaction() -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection inside an IMMEDIATE transaction for write operations."""
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
