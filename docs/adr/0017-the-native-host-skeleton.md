# 0017 — The native host skeleton, and what a second language found

Status: accepted
Date: 2026-08-11

## Context

`CLAUDE.md` puts a signed native host in phase 1.5, owning TCC-facing
capabilities eventually, and the Tauri UI in phase 3. The protocol artifact
existed with exactly one reader, which is the same as having no artifact.

## Decision

**A plain Rust binary, not Tauri.** `native/` is a crate with a socket client
and a terminal front end. No webview, no npm, no build pipeline.

**Rust types are generated from `ev.schema.json` by `cargo typify` and
committed** to `protocol/generated/rust/`. `make protocol-check-rust` fails on
a stale artifact and CI runs it, on both Linux and macOS.

**The client dispatches on `type`, not on the shape of a message.**

**The binary is signed with the Apple Development identity**, hardened runtime,
via `make sign`. Signing stays local; CI builds unsigned.

**No capability is implemented.** No audio, no camera, no Accessibility, no
Apple Events.

## What the second language found

**An event could be mistaken for a response.** `confirmation.required` carries
an `id` of its own — the confirmation's, not the request's — and both clients
were correlating replies by matching `id`. One implementation can be
self-consistent about a shape that is not actually unambiguous; writing the
second one is what surfaced it. Both now treat any message carrying `type` as
an event, since a response never has one. There is a test on each side.

**The generated unions are untagged.** The schema declares
`discriminator: {propertyName: type}`, and `typify` emits `#[serde(untagged)]`,
which matches by field shape. It works today only because the messages'
required fields differ, and would break the moment two shared a shape. Nothing
in the client relies on those unions.

**The length bound crossed the boundary.** `text` is 1–4000 characters in
Pydantic, and the generated Rust carries the same bound as a newtype. One
declaration, two languages, with a test proving it.

## Alternatives rejected

**Scaffolding Tauri now.** Phase 3 is the UI. A webview and a JS toolchain in
phase 1.5 would be a framework with nothing to render, and the host's actual
job here — speak the protocol, hold a signature — needs none of it.

**Hand-writing the Rust types.** Faster today, and it makes the committed
schema decorative: two hand-maintained views agree until someone edits one.

**Signing later, when a capability needs it.** TCC keys grants to a code
signature. An unsigned host is re-prompted on every rebuild and can never hold
a stable microphone or Apple Events grant, so the identity has to exist before
the first capability, not after.

**Loosening the crate's lint rules to accommodate generated code.** The crate
denies all of clippy. The generated module gets a scoped `#[allow(...)]` for
the lints its output trips; the code we write stays strict.

## Consequences

Verified end to end: the Rust host drove the Python daemon through three turns
— a browser tool that ran, a music tool refused for a missing `apple_events`
grant, and an utterance nothing routed — with correct exit codes and both
actions in the journal.

The signature is `Apple Development: gggonzaga@icloud.com`, team
`C7K67DZ94H`, hardened runtime. That is a development certificate: fine for a
locally-run host, and not distribution. A **Developer ID Application**
certificate and notarisation are phase 3+ and need a paid membership.

`native/` depends on the generated schema and never on the Python. The two
processes share an artifact, not a language, which is the only arrangement in
which "single source of truth for three languages" means anything.

CI now caches `cargo-typify`, which is compiled from source; without it every
run would spend minutes rebuilding a tool that never changes.
