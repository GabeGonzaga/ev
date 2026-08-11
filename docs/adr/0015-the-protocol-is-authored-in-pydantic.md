# 0015 — The protocol is authored in Pydantic and shipped as JSON Schema

Status: accepted
Date: 2026-08-11

## Context

`CLAUDE.md`: schemas live in `protocol/` and are the single source of truth for
three languages; `protocol/generated/` is committed and CI regenerates and
fails on any diff.

Three languages have to agree, and only one of them runs this test suite.

## Decision

**Pydantic authors, JSON Schema ships.** `protocol/messages.py` is written by
hand; `protocol/generated/ev.schema.json` is produced from it and committed.
Rust and TypeScript will read the artifact, never the Python.

**`make protocol` regenerates; `make protocol-check` fails on a stale
artifact, and `lint` depends on it.** A test asserts the same thing, so it
fails in the suite as well as the build.

**Commands and events are separate families.** Commands travel native→Python,
carry an `id`, and are answered exactly once. Events travel Python→native, have
no `id`, and are not answered.

**Every message forbids unknown fields**, and the union is discriminated on
`type`, so a host speaking a newer protocol fails loudly.

**The handshake compares `PROTOCOL_VERSION` exactly.**

## Alternatives rejected

**Hand-written JSON Schema as the source.** Neutral, and miserable to author:
`$defs`, `$ref` and discriminated unions by hand, with no type checking while
writing them, for a document that already has a good generator. The neutrality
is preserved anyway — the artifact is the contract, and nothing downstream sees
the Python.

**Generating the Python from the schema too, for symmetry.** It would make all
three languages equal and make the Python worse: these types reference
`RiskLevel`, `Permission` and `PermissionState` from `ev/domain/`, and a
generator would emit its own copies, so the daemon would translate between two
spellings of the same enum at the boundary.

**Producing the artifact at build time instead of committing it.** Then a
protocol change is invisible in review — the diff that matters most, the one
three languages read, would exist only on the machine that built it.

**One envelope for both directions.** Every message would carry an `id` that is
meaningless in one of them, and a reader could not tell whether silence is an
answer or an event that never comes.

**Allowing unknown fields for forward compatibility.** Tempting for a protocol,
wrong for this one: the host is spawned by us and versioned by handshake, so an
unknown field means a mismatch that the handshake should already have refused.

## Consequences

The staleness check was verified by breaking it: adding a field to
`SpeechRequested` makes `make protocol-check` and `make lint` fail with the
regeneration command in the message.

`protocol/` imports from `ev/domain/`. That is deliberate — the wire spelling of
`risk` and `permission` is the domain's spelling, and one definition beats two —
but it is a dependency to watch: if the protocol ever needs a shape the domain
does not have, the answer is a new type in the protocol, not a change to the
domain to suit the wire.

Rust and TypeScript generation is not here. The artifact exists and is stable;
the generators arrive with the native host that consumes them, and adding a Rust
or Node toolchain to CI before either exists would be infrastructure with no
consumer.
