from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ev.domain.results import ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel
from ev.infrastructure.database.connection import connect
from ev.infrastructure.database.journal import SqliteJournal
from ev.infrastructure.database.migrations import migrate
from ev.registry import CallRecord

pytestmark = pytest.mark.asyncio


class Clock:
    """Stamps a distinct, ordered time per call, so the tests can tell when a
    record was taken from when it was written."""

    def __init__(self) -> None:
        self.start = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        self.ticks = 0

    def __call__(self) -> datetime:
        self.ticks += 1
        return self.start + timedelta(seconds=self.ticks)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "ev.db")
    migrate(connection)
    yield connection
    connection.close()


def call(
    *,
    tool: str = "browser.open_url",
    risk: RiskLevel = RiskLevel.SAFE,
    result: ToolResult | None = None,
    arguments: dict[str, object] | None = None,
) -> CallRecord:
    return CallRecord(
        tool=tool,
        risk=risk,
        arguments=arguments or {"url": "https://a.test"},
        result=result or ToolResult.success(tool, speech="Opening it"),
        urgent=risk is RiskLevel.DESTRUCTIVE,
    )


def rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute("SELECT * FROM journal ORDER BY id").fetchall()


async def test_a_flushed_record_lands_with_every_column_set(
    connection: sqlite3.Connection,
) -> None:
    journal = SqliteJournal(connection, clock=Clock())

    await journal.record(call())
    await journal.flush()

    (row,) = rows(connection)
    assert row["tool"] == "browser.open_url"
    assert row["risk"] == "safe"
    assert row["ok"] == 1
    assert row["error_code"] is None
    assert row["error_message"] is None
    assert json.loads(row["arguments"]) == {"url": "https://a.test"}
    assert json.loads(row["data"]) == {}
    assert row["speech"] == "Opening it"
    assert row["recorded_at"] == "2026-08-10T09:00:01+00:00"


async def test_ordinary_calls_are_batched(connection: sqlite3.Connection) -> None:
    journal = SqliteJournal(connection, batch_size=3)

    await journal.record(call())
    await journal.record(call())

    assert rows(connection) == []

    await journal.record(call())

    assert len(rows(connection)) == 3


async def test_a_destructive_call_is_flushed_immediately(
    connection: sqlite3.Connection,
) -> None:
    # Invariant 5: the record of an irreversible action must not be sitting in
    # a list when the process dies.
    journal = SqliteJournal(connection, batch_size=100)

    await journal.record(call(tool="system.empty_trash", risk=RiskLevel.DESTRUCTIVE))

    assert len(rows(connection)) == 1


async def test_an_urgent_flush_carries_everything_pending_with_it(
    connection: sqlite3.Connection,
) -> None:
    journal = SqliteJournal(connection, batch_size=100)

    await journal.record(call())
    await journal.record(call(tool="system.empty_trash", risk=RiskLevel.DESTRUCTIVE))

    assert [row["tool"] for row in rows(connection)] == [
        "browser.open_url",
        "system.empty_trash",
    ]


async def test_records_are_timestamped_when_taken_not_when_written(
    connection: sqlite3.Connection,
) -> None:
    journal = SqliteJournal(connection, batch_size=100, clock=Clock())

    await journal.record(call())
    await journal.record(call())
    await journal.flush()

    assert [row["recorded_at"] for row in rows(connection)] == [
        "2026-08-10T09:00:01+00:00",
        "2026-08-10T09:00:02+00:00",
    ]


async def test_failures_are_recorded_with_their_code(
    connection: sqlite3.Connection,
) -> None:
    journal = SqliteJournal(connection)

    await journal.record(
        call(
            result=ToolResult.failure(
                "browser.open_url",
                ToolErrorCode.ADAPTER_FAILED,
                "open exited 1",
            )
        )
    )
    await journal.flush()

    (row,) = rows(connection)
    assert row["ok"] == 0
    assert row["error_code"] == "adapter_failed"
    assert row["error_message"] == "open exited 1"


async def test_unserialisable_arguments_do_not_lose_the_record(
    connection: sqlite3.Connection,
) -> None:
    # The raw proposal recorded on INVALID_ARGUMENTS has not been normalised,
    # so it can hold anything. The trail is worth more than a clean encoding.
    journal = SqliteJournal(connection)

    await journal.record(call(arguments={"when": datetime(2026, 8, 10, tzinfo=UTC)}))
    await journal.flush()

    (row,) = rows(connection)
    assert json.loads(row["arguments"]) == {"when": "2026-08-10 00:00:00+00:00"}


async def test_flushing_nothing_is_a_no_op(connection: sqlite3.Connection) -> None:
    journal = SqliteJournal(connection)

    await journal.flush()

    assert rows(connection) == []


async def test_a_failed_write_keeps_the_records_pending(
    connection: sqlite3.Connection,
) -> None:
    journal = SqliteJournal(connection, batch_size=100)
    await journal.record(call())

    connection.execute("DROP TABLE journal")
    with pytest.raises(sqlite3.OperationalError):
        await journal.flush()

    # The record survived the failure and lands once the table is back.
    connection.execute("PRAGMA user_version = 0")
    migrate(connection)
    await journal.flush()

    assert len(rows(connection)) == 1


async def test_history_reads_back_newest_first(connection: sqlite3.Connection) -> None:
    journal = SqliteJournal(connection, clock=Clock())
    await journal.record(call(tool="browser.open_url"))
    await journal.record(call(tool="music.play", risk=RiskLevel.SENSITIVE))

    entries = await journal.recent()

    assert [entry.tool for entry in entries] == ["music.play", "browser.open_url"]
    assert entries[0].risk is RiskLevel.SENSITIVE
    assert entries[0].arguments == {"url": "https://a.test"}
    assert entries[0].speech == "Opening it"


async def test_history_flushes_before_it_reads(
    connection: sqlite3.Connection,
) -> None:
    # The batch exists so the voice path does not commit per turn. It would be
    # a strange history that omitted what just happened.
    journal = SqliteJournal(connection, batch_size=100)
    await journal.record(call())

    assert rows(connection) == []
    assert len(await journal.recent()) == 1


async def test_history_pages_backwards(connection: sqlite3.Connection) -> None:
    journal = SqliteJournal(connection)
    for index in range(5):
        await journal.record(call(tool=f"a.b{index}"))
    await journal.flush()

    newest = await journal.recent(limit=2)
    older = await journal.recent(limit=2, before=newest[-1].id)

    assert [entry.tool for entry in newest] == ["a.b4", "a.b3"]
    assert [entry.tool for entry in older] == ["a.b2", "a.b1"]


async def test_a_failure_keeps_its_reason_in_the_trail(
    connection: sqlite3.Connection,
) -> None:
    journal = SqliteJournal(connection)
    await journal.record(
        call(
            result=ToolResult.failure(
                "music.play", ToolErrorCode.PERMISSION_DENIED, "needs apple_events"
            )
        )
    )

    (entry,) = await journal.recent()

    assert entry.ok is False
    assert entry.error_code == "permission_denied"
    assert entry.error_message == "needs apple_events"
