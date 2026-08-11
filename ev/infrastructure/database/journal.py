"""The audit trail: every call that reached a tool, and how it ended.

Ordinary calls are batched, because the voice path is budgeted in milliseconds
and a commit per turn buys nothing. Destructive calls are flushed immediately
(invariant 5): the record of an irreversible action must not be sitting in a
list when the process dies.

Records are timestamped when they happen, not when they are written, so
batching never distorts the order or the times in the trail.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from ev.domain.journal import JournalEntry
from ev.domain.risk import RiskLevel
from ev.registry import CallRecord

_RECENT = """
SELECT id, recorded_at, tool, risk, ok, error_code, error_message,
       arguments, speech
FROM journal
WHERE (:before IS NULL OR id < :before)
ORDER BY id DESC
LIMIT :limit
"""

_INSERT = """
INSERT INTO journal (
    recorded_at, tool, risk, ok, error_code, error_message,
    arguments, data, speech
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SqliteJournal:
    """Implements `JournalPort`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        batch_size: int = 20,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._connection = connection
        self._batch_size = batch_size
        self._clock = clock
        self._pending: list[tuple[object, ...]] = []

    async def record(self, record: CallRecord) -> None:
        self._pending.append(self._row(record))
        if record.urgent or len(self._pending) >= self._batch_size:
            await self.flush()

    async def flush(self) -> None:
        if not self._pending:
            return

        self._connection.execute("BEGIN")
        try:
            self._connection.executemany(_INSERT, self._pending)
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

        # Cleared only after the commit, so a failed write is still pending.
        self._pending.clear()

    async def recent(
        self, *, limit: int = 20, before: int | None = None
    ) -> list[JournalEntry]:
        """The last few turns, newest first.

        Flushes first. The batch exists so the voice path does not commit per
        turn, and it would be a strange history that omitted what just
        happened.
        """
        await self.flush()

        rows = self._connection.execute(
            _RECENT, {"limit": max(1, min(limit, 500)), "before": before}
        ).fetchall()

        return [
            JournalEntry(
                id=row["id"],
                recorded_at=row["recorded_at"],
                tool=row["tool"],
                risk=RiskLevel(row["risk"]),
                ok=bool(row["ok"]),
                arguments=json.loads(row["arguments"]),
                speech=row["speech"],
                error_code=row["error_code"],
                error_message=row["error_message"],
            )
            for row in rows
        ]

    def _row(self, record: CallRecord) -> tuple[object, ...]:
        result = record.result
        return (
            self._clock().isoformat(),
            record.tool,
            record.risk.value,
            int(result.ok),
            result.error.code.value if result.error else None,
            result.error.message if result.error else None,
            # default=str: on INVALID_ARGUMENTS these are the raw proposal, and
            # the trail is worth more than a serialisation error.
            json.dumps(record.arguments, default=str, sort_keys=True),
            json.dumps(result.data, default=str, sort_keys=True),
            result.speech,
        )
