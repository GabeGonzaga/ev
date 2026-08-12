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
    Migration(
        version=2,
        name="journal search",
        statements=(
            # External content: the text lives in `journal` and the index
            # points at it, so nothing is stored twice and the trail stays the
            # one source of truth.
            #
            # `remove_diacritics 2` is why "marco" finds "Março". Whisper
            # writes accents inconsistently on short utterances and nobody
            # types them into a search box, so folding them is the difference
            # between finding a turn and being told it never happened.
            """
            CREATE VIRTUAL TABLE journal_fts USING fts5(
                tool,
                arguments,
                speech,
                content='journal',
                content_rowid='id',
                tokenize="unicode61 remove_diacritics 2"
            )
            """,
            # Everything already recorded, indexed in place. A search that
            # only knew about turns taken after an upgrade would be worse than
            # no search: it would answer, and be wrong.
            """
            INSERT INTO journal_fts (rowid, tool, arguments, speech)
            SELECT id, tool, arguments, speech FROM journal
            """,
            """
            CREATE TRIGGER journal_ai AFTER INSERT ON journal BEGIN
                INSERT INTO journal_fts (rowid, tool, arguments, speech)
                VALUES (new.id, new.tool, new.arguments, new.speech);
            END
            """,
            # The journal is append-only today. These two exist so that stays
            # a property of the code rather than a thing the index depends on:
            # an external-content index left behind by a delete answers with
            # rows that are not there any more.
            """
            CREATE TRIGGER journal_ad AFTER DELETE ON journal BEGIN
                INSERT INTO journal_fts (journal_fts, rowid, tool, arguments, speech)
                VALUES ('delete', old.id, old.tool, old.arguments, old.speech);
            END
            """,
            """
            CREATE TRIGGER journal_au AFTER UPDATE ON journal BEGIN
                INSERT INTO journal_fts (journal_fts, rowid, tool, arguments, speech)
                VALUES ('delete', old.id, old.tool, old.arguments, old.speech);
                INSERT INTO journal_fts (rowid, tool, arguments, speech)
                VALUES (new.id, new.tool, new.arguments, new.speech);
            END
            """,
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
