# 0024 — Macros are validated lists of tool calls

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 4

## Context

`CLAUDE.md` rules out creating Shortcuts programmatically: `.shortcut` files
are encrypted, there is no public format and no creation API. It names the
answer — "E.V.'s own JSON macro format: a named list of validated tool calls
that E.V. can create, edit, validate, version, import, export and run".

The risk is that a macro becomes a second execution path. A list of calls
stored on disk is exactly the shape of a thing that grows its own runner, its
own permission handling and its own idea of what a tool is.

## Decision

A macro is a `Macro` model — name, optional description, version, and between
1 and 50 `MacroStep`s. It lives in `macros.json` beside the database, not in
the repository and not in the database: it is a file the user edits.

`macro.run` is an ordinary tool in an ordinary capability. `MacroService`
holds the same `Registry.call` the assistant holds, so every step goes through
the one door: args-model validation, policy, confirmation, journal. A macro
cannot reach a tool the utterance could not, cannot skip a confirmation, and
appears in the journal as its steps rather than as one opaque entry.

`macro.run` itself claims no permissions and is `SAFE`. The step it runs
claims what it claims. Declaring the union up front would either over-refuse
(a macro of two safe steps asking for Apple Events) or, worse, pre-authorise.

A macro stops at the first failing step and says which step, which tool and
why. Continuing past a failure would mean guessing that the rest is still
meaningful.

`ev --macros` lists the saved macros and validates every step against
`Registry.spec()`, exiting non-zero if one does not validate — the same
Pydantic model the router validates against, so a macro cannot be wrong in a
way a routed call could not be.

## Alternatives rejected

**Steps in SQLite.** The journal is E.V.'s, the database is E.V.'s. A macro is
the user's, and a file they can open, diff and copy to another machine is
worth more than a table.

**A macro runner beside `Registry.call()`.** This is invariant 4. It is also
where the permission model would have quietly forked.

**Step chaining — feeding one step's result into the next.** Not now. The
moment a result becomes an argument, `Content` enforcement stops being
deferred: generated text would be one step away from selecting a target.
Chaining lands with that enforcement or not at all.

**Recording a macro from history.** Attractive, and it needs the same
validation that already exists. It is additive; nothing here blocks it.
