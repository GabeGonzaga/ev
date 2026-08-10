# 0001 — `Resolution` lives in `ev/domain/`, not `ev/router/`

Status: accepted
Date: 2026-08-10

## Context

`CLAUDE.md` defines `Resolution` inside the routing section, and the repository
layout it prescribes lists exactly three files under `ev/domain/`:
`results.py`, `permissions.py`, `risk.py`. Taken literally, `Resolution` would
live in `ev/router/`.

But `Resolution` crosses a seam. `StaticRouter.resolve()` produces it, the
model router will produce the same type in phase 1, and `Assistant.handle()`
consumes it. It is the vocabulary of the router→application boundary, not an
internal detail of either side.

## Decision

`Resolution` goes in `ev/domain/resolution.py`, a fourth file under `domain/`.

## Alternatives rejected

**`ev/router/types.py`.** Follows the documented layout literally, but makes
`ev/application/assistant.py` import from `ev/router/` to name its own input.
The application layer would then depend on the router package to describe what
it accepts, which inverts the direction the layering is meant to enforce: the
router is a supplier of proposals, and swapping tier implementations should not
touch the application's imports.

**`ev/application/`.** Same problem mirrored — the router would import from the
application layer to name its own return type.

**Defining it twice, once per side.** Two definitions of one wire shape drift,
and phase 1.5 generates the IPC schemas from these types.

## Consequences

`ev/domain/` now holds four files instead of the three named in `CLAUDE.md`.
The layout section there is a description of the design, and this file records
where the description was extended and why. The rule it was extended under is
the one already stated for the layer: "types shared across layers, no I/O" —
which is precisely what `Resolution` is.

Nothing else moves. `Resolution` carries no tier or provenance field; the
journal records which tier answered, because that is an execution fact rather
than a property of the proposal.
