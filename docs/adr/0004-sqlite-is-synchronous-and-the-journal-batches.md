# 0004 — SQLite calls are synchronous, and the journal batches all but destructive

Status: accepted
Date: 2026-08-10

## Context

The core is `asyncio` and owns no threads. `sqlite3` is a blocking driver. The
journal port is `async def record(...)`, and every turn writes to it.

## Decision

**`sqlite3` is called synchronously, directly inside the `async` methods.** No
thread pool, no async driver.

**The port stays `async`.** Only the current implementation is synchronous.

**Ordinary records are batched (default 20); `urgent` records flush at once.**
`urgent` is set by the registry for `DESTRUCTIVE` calls.

**Records are timestamped when taken, not when written.**

**The applied schema version is `PRAGMA user_version`**, not a migrations table.

## Alternatives rejected

**`asyncio.to_thread` for each query.** It is the reflex, and here it buys
nothing: a WAL commit at `synchronous = NORMAL` on local SSD is in the same
order of magnitude as the thread hop and the GIL round-trip needed to await it,
so the loop is blocked either way, only later and less predictably. It also
introduces exactly the thing the core is not supposed to have — a pool of
threads the application manages — for a write that is not the bottleneck in a
1.8 s budget.

**`aiosqlite`.** A dependency whose implementation is a thread per connection.
The same trade with the threads hidden one layer down.

**Making the port synchronous to match.** Honest today, wrong tomorrow: the
journal is the one component most likely to acquire real I/O later (a remote
sink, an fsync policy, a retry), and unwinding `async` through `Registry.call()`
afterwards touches every caller. The asymmetry is deliberate — the port
describes the contract, not the current driver.

**Journalling every call immediately.** A commit per turn on the voice path,
for a trail nobody reads in real time. Batching is why the flush distinction in
invariant 5 exists at all: if everything were urgent, "urgent" would mean
nothing.

**Timestamping at flush time.** Simpler, and it would make batching visible in
the data — a burst of calls collapsing to one instant, ordered by whenever the
buffer happened to drain. The trail exists to answer "what did E.V. do and
when"; that answer must not depend on the buffer.

**A `schema_migrations` table.** More auditable, and it can disagree with the
file it describes — a database restored or copied without it looks unmigrated.
`user_version` lives in the SQLite header, so the version travels with the
schema. For a single-file, single-user, local database that is worth more than
the audit row.

## Consequences

A crash loses at most the pending non-destructive tail — calls that already
happened but were not yet written. That is the accepted cost of batching, and
the reason destructive calls do not take it. The CLI and, later, the daemon must
flush on shutdown.

`SqliteJournal.flush()` clears its buffer only after `COMMIT`, so a failed write
keeps the records pending rather than dropping them. It re-raises: ADR 0002 says
an unrecorded action is a defect, and that still holds here.

Migrations are append-only. Editing one that has shipped changes the schema of
databases that already ran it and will not re-run it. A test asserts the
versions are contiguous from 1, so a dropped or duplicated migration fails the
build rather than the user's database.
