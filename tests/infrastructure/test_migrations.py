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

    assert [row["name"] for row in tables] == ["journal"]


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
