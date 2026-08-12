from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ev.infrastructure.database.connection import connect
from ev.infrastructure.database.migrations import (
    MIGRATIONS,
    migrate,
    schema_version,
)


@pytest.fixture
def connection(tmp_path: Path) -> sqlite3.Connection:
    # A real file, not :memory: -- WAL is a no-op in memory, and the suite
    # should exercise the mode the application actually runs in.
    return connect(tmp_path / "ev.db")


def test_connect_enables_wal(connection: sqlite3.Connection) -> None:
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_connect_creates_the_directory(tmp_path: Path) -> None:
    connect(tmp_path / "nested" / "deeper" / "ev.db")

    assert (tmp_path / "nested" / "deeper" / "ev.db").exists()


def test_migrate_reports_and_records_the_version(
    connection: sqlite3.Connection,
) -> None:
    assert schema_version(connection) == 0

    assert migrate(connection) == MIGRATIONS[-1].version
    assert schema_version(connection) == MIGRATIONS[-1].version


def test_migrate_is_idempotent(connection: sqlite3.Connection) -> None:
    migrate(connection)
    migrate(connection)

    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()

    # `journal_fts` is one virtual table; the rest are the shadow tables FTS5
    # keeps for it. They are listed here rather than filtered out so that a
    # table appearing for any other reason fails this test.
    assert [row["name"] for row in tables] == [
        "journal",
        "journal_fts",
        "journal_fts_config",
        "journal_fts_data",
        "journal_fts_docsize",
        "journal_fts_idx",
    ]


def test_the_index_is_backfilled_from_what_is_already_there(
    tmp_path: Path,
) -> None:
    """A database written before the search existed is searchable after it.

    A search that only knew about turns taken since an upgrade would be worse
    than no search: it would answer, and be wrong.
    """
    connection = connect(tmp_path / "ev.db")
    for statement in MIGRATIONS[0].statements:
        connection.execute(statement)
    connection.execute("PRAGMA user_version = 1")
    connection.execute(
        "INSERT INTO journal (recorded_at, tool, risk, ok, arguments, data, speech)"
        " VALUES ('2026-01-01T00:00:00Z', 'music.play', 'sensitive', 1,"
        " '{\"name\": \"Blonde\"}', '{}', 'Playing Blonde')"
    )

    migrate(connection)

    found = connection.execute(
        "SELECT rowid FROM journal_fts WHERE journal_fts MATCH '\"blonde\"'"
    ).fetchall()
    assert len(found) == 1


def test_a_deleted_row_leaves_no_ghost_in_the_index(
    connection: sqlite3.Connection,
) -> None:
    # The journal is append-only today. The trigger is what keeps that a
    # property of the code rather than something the index depends on: an
    # external-content index outliving its rows answers with turns that are
    # not there any more.
    migrate(connection)
    connection.execute(
        "INSERT INTO journal (recorded_at, tool, risk, ok, arguments, data, speech)"
        " VALUES ('2026-01-01T00:00:00Z', 'music.play', 'sensitive', 1,"
        " '{\"name\": \"Blonde\"}', '{}', 'Playing Blonde')"
    )

    connection.execute("DELETE FROM journal")

    found = connection.execute(
        "SELECT rowid FROM journal_fts WHERE journal_fts MATCH '\"blonde\"'"
    ).fetchall()
    assert found == []


def test_the_journal_table_has_the_expected_columns(
    connection: sqlite3.Connection,
) -> None:
    migrate(connection)

    columns = connection.execute("PRAGMA table_info(journal)").fetchall()

    assert [row["name"] for row in columns] == [
        "id",
        "recorded_at",
        "tool",
        "risk",
        "ok",
        "error_code",
        "error_message",
        "arguments",
        "data",
        "speech",
    ]


def test_migration_versions_are_contiguous_from_one() -> None:
    # A gap or a duplicate means a migration was edited or dropped after
    # shipping, which silently changes the schema of databases in the field.
    assert [migration.version for migration in MIGRATIONS] == list(
        range(1, len(MIGRATIONS) + 1)
    )


def test_a_failing_migration_leaves_no_partial_schema(
    connection: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = (
        MIGRATIONS[0].__class__(
            version=1,
            name="broken",
            statements=("CREATE TABLE fine (id INTEGER)", "THIS IS NOT SQL"),
        ),
    )
    monkeypatch.setattr(
        "ev.infrastructure.database.migrations.MIGRATIONS", broken, raising=True
    )

    with pytest.raises(sqlite3.OperationalError):
        migrate(connection)

    assert schema_version(connection) == 0
    assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []
