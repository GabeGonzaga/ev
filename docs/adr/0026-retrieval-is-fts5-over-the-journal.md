# 0026 — Retrieval is FTS5 over the journal

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 4

## Context

`CLAUDE.md`: "SQLite is the only database. WAL mode, FTS5, `sqlite-vec` only
when retrieval actually lands." `ARCHITECTURE.md` names the trigger for FTS5 as
retrieval landing, which is this.

The question retrieval had to answer first was *what corpus*. E.V. has exactly
one: the journal. Every turn it has taken, with the tool, the arguments and the
line it said. Nothing else on this machine is E.V.'s to index.

## Decision

Migration 2 adds `journal_fts`, an external-content FTS5 table over `journal`.
External content means the text is stored once — the journal stays the single
source of truth and the index points into it.

`tokenize="unicode61 remove_diacritics 2"`. This is not a nicety in pt-PT:
whisper writes accents inconsistently on short utterances and nobody types them
into a search box. "marco" finds "Março" in both directions.

The migration backfills. A search that only knew about turns taken since an
upgrade would be worse than no search, because it would answer and be wrong.

Insert, update and delete triggers keep the index honest. The journal is
append-only today; the triggers are what stop that being something the index
silently depends on.

Results come back newest first, not by `bm25`. Someone searching their own
history is asking *when* they did something; ranking would put a turn from
March above yesterday's for saying "Blonde" twice.

`fts_query()` builds the MATCH expression. FTS5's argument is a query language
— `AND`, `NEAR`, `^`, `*`, `:`, quoted phrases — so passing someone's words to
it unchanged makes "blonde AND" an exception and "name:" a column filter. Every
token is quoted, which makes it a literal, and only the last gets a prefix `*`
so a word still being typed matches. This is the same rule as everywhere else
in E.V.: the caller supplies values, never syntax.

One reach across all three surfaces, because a search that only the CLI can do
is not retrieval landing: `ev --find TEXT`, protocol 1.3 (`history.query` gains
`query`), `GET /api/history?q=`, and a search box in the panel. The `History`
port gained one argument and the journal one method; nothing else moved.

### A defect this found

Journal arguments were written with `json.dumps` defaults, so `Março` was
stored as `Março`. The trail was unreadable in a SQLite browser, and the
index tokenised it as `Mar` and `u00e7o` — searching for the word in either
spelling would have found nothing. Now `ensure_ascii=False`: SQLite stores
UTF-8 and there was never anything to escape it for.

## Alternatives rejected

**`sqlite-vec` now.** Semantic search needs an embedding model resident or
spawned per query, and the latency budget already says not to hold a second
model. FTS5 answers "when did I play Blonde" exactly; it is "what did I do
about the boiler" that needs vectors, and that question needs more of a corpus
than a journal of tool calls. It stays on the trigger list.

**Ranking by relevance.** Measured against the question people actually ask of
a history, `ORDER BY id DESC` is the right answer and needs no explaining.

**A `history.search` tool, reachable by voice.** "What did I do yesterday" is a
real request and it needs date parsing, a spoken summary and a decision about
how much of the trail a voice answer should read out. Those are three decisions,
none of which retrieval had to settle to land.

**Indexing `data` as well as `arguments`.** `data` is what a tool returned,
which is mostly ids and booleans. It would grow the index and match nothing
anyone would search for.
