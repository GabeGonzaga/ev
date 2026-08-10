"""Opening the one database.

SQLite is the only database (invariant 11), it lives in
`~/Library/Application Support/EV/`, and it is never in the repository.

Calls here are synchronous. See ADR 0004: a local WAL commit is faster than
the thread hop that would be needed to await it, and the core owns no threads.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

APPLICATION_SUPPORT = Path.home() / "Library" / "Application Support" / "EV"


def default_database_path() -> Path:
    """macOS only. Everything else injects a path -- which is what the suite
    does, so it runs on Linux."""
    return APPLICATION_SUPPORT / "ev.db"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)

    # isolation_level=None: no implicit transactions. Every write below says
    # BEGIN and COMMIT where it means them.
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    return connection
