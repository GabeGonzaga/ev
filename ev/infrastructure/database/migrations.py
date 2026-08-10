"""Schema migrations, applied in order, each in its own transaction.

The applied version is `PRAGMA user_version`. SQLite keeps it in the file
header, so the schema version travels with the database and cannot disagree
with it.

A migration is append-only. Editing one that has shipped changes the schema of
databases that already ran it and will not be re-run.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="journal",
        statements=(
            """
            CREATE TABLE journal (
                id            INTEGER PRIMARY KEY,
                recorded_at   TEXT    NOT NULL,
                tool          TEXT    NOT NULL,
                risk          TEXT    NOT NULL,
                ok            INTEGER NOT NULL,
                error_code    TEXT,
                error_message TEXT,
                arguments     TEXT    NOT NULL,
                data          TEXT    NOT NULL,
                speech        TEXT
            )
            """,
            "CREATE INDEX journal_recorded_at ON journal (recorded_at)",
            "CREATE INDEX journal_tool ON journal (tool)",
        ),
    ),
)


def schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    version: int = row[0]
    return version


def migrate(connection: sqlite3.Connection) -> int:
    """Apply every migration newer than the file's version. Returns the new one."""
    current = schema_version(connection)

    for migration in MIGRATIONS:
        if migration.version <= current:
            continue

        connection.execute("BEGIN")
        try:
            for statement in migration.statements:
                connection.execute(statement)
            # PRAGMA takes no parameters; the value is an int from this module,
            # never from input. DDL is transactional in SQLite, so a failure
            # here rolls back the schema change with it.
            connection.execute(f"PRAGMA user_version = {migration.version:d}")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")

        current = migration.version

    return current
