# Architecture

What exists today, and what has to be true before each piece grows. `CLAUDE.md`
states the invariants; this file states the current shape and the triggers.

## The turn

```text
utterance (verbatim, any language)
    │
    ▼
StaticRouter.resolve()          tier 0 learned phrases, tier 1 regex
    │   Resolution | None       None means "not mine"
    ▼
ModelRouter.resolve()           tier 2, only on a static miss
    │   Resolution | None       tool is an enum, or null to decline
    ▼
ConfidencePolicy                >= 0.7 act · >= 0.4 ask · below, refuse
    │
    ▼
Assistant.handle()              ToolResult | Clarification | None
    │
    ▼
Registry.call()                 the single door
    │
    ├── args model validation   raw input never goes further than this
    ├── PermissionPolicy        permission state, then risk
    ├── ConfirmationPort        always for DESTRUCTIVE, whatever the policy said
    ├── handler                 the capability's service, given a model instance
    └── JournalPort             every outcome, urgent when destructive
    │
    ▼
ToolResult
```

Only `Registry.call()` authorises execution. There is no second path, and
nothing below it takes a `dict` — a handler receives its validated args model.

## Layers

| Layer | May depend on | May not |
|---|---|---|
| `ev/domain/` | nothing | everything |
| `ev/application/` | domain | infrastructure, capabilities |
| `ev/router/` | domain | everything else |
| `ev/registry.py` | domain, application | infrastructure, capabilities |
| `ev/capabilities/` | domain, registry, infrastructure | other capabilities |
| `ev/infrastructure/` | domain, registry | application, capabilities, router |

`tests/test_architecture.py` enforces the parts of this that can be checked:
no outside-world imports above infrastructure, and no shell API anywhere.

Ports are declared by the consumer. `Registry` names `PolicyPort`,
`ConfirmationPort` and `JournalPort`; the application and infrastructure layers
satisfy them structurally, which is why neither imports the other.

## One door per subsystem

Each subsystem has one public port. Today there are three:

| Port | Owns |
|---|---|
| `ProcessRunner` | every subprocess. argv only — no shell, no `cwd`, no `env` |
| `AppleScriptClient` | every AppleScript. Constant source, values as `argv` |
| `OllamaClient` | every model call, both paths. Local HTTP, model from config |

`AppleScriptClient` goes through `ProcessRunner` rather than around it.

`AccessibilityClient`, `ShortcutsClient` and `NativeBridge` are named in
`CLAUDE.md` and do not exist yet. They arrive with the capability that needs
them, not before.

## Triggers

Nothing below gets built until its trigger fires. Building earlier produces
structure shaped by symmetry rather than by a decision.

| Change | Trigger |
|---|---|
| `capabilities/<cap>/adapters.py` → `adapters/` | a second adapter in that capability |
| A new capability directory | its first tool lands |
| `ev/router/` gains a module | tier 2 arrives (phase 1) |
| `PolicyDecision` gains `REQUEST_PERMISSION` | a native host exists that can service it |
| A journal read API | something reads history — the CLI or phase 3 |
| Enforcing the `Content` marker | tools feed each other — macros, phase 4 |
| Streaming model responses | something can render a partial answer |
| `sqlite-vec`, FTS5 | retrieval actually lands (phase 4) |
| `protocol/` | phase 1.5 |
| A second resident model | never on the interactive path |

## What does not exist yet

No voice, no native host, no UI.

Tier 2, the generation path and `make eval` exist. `qwen3:8b` is the measured
default (ADR 0013): 17/18 routing, 0/8 inventions, 10/10 arguments accepted.

Two findings hold across four models. Self-reported confidence carries almost
no information — every model rates its wrong answers 1.00 as readily as its
right ones (ADR 0012). And **the model path is over budget**: 2.06 s median
against the 900 ms allotted to the router. That makes every tier 1 hit worth
~2 s, not the ~900 ms the tiering was justified with.

The suite reaches no model at all. An autouse fixture fails any test that would
open a socket to Ollama, because that test would pass or fail according to
whose machine ran it.

A tool declaring a TCC permission is denied until the user asserts the grant
(`--grant`, ADR 0007) or, from phase 1.5, a host reports it. `music.play`
declares `APPLE_EVENTS` and takes that path; `browser.open_url` declares
nothing, because `open(1)` needs nothing.

## Testing shape

- Adapter tests assert on **exact argv**, through fake executables in
  `tests/fakes/bin/` prepended to `PATH`. Nothing mocks `subprocess`.
- Routing has **golden cases** in `evals/routing/*.jsonl`, PT and EN for every
  intent, including the utterances that must *not* route.
- Database tests run against a real file, not `:memory:` — WAL is a no-op in
  memory.
- The suite runs on Linux. That is the fast feedback loop, and it is why every
  macOS boundary is behind a port. CI runs `make test` and `make lint` on
  `ubuntu-latest` and `macos-latest`; a test that passes only on the Mac means
  a boundary escaped its port.

## Decisions

| ADR | |
|---|---|
| [0001](adr/0001-resolution-lives-in-domain.md) | `Resolution` lives in `domain/` |
| [0002](adr/0002-the-registry-owns-its-ports.md) | The registry owns its ports and confirms destructive calls itself |
| [0003](adr/0003-the-permission-policy.md) | The permission policy denies on unknown state |
| [0004](adr/0004-sqlite-is-synchronous-and-the-journal-batches.md) | SQLite is synchronous; the journal batches |
| [0005](adr/0005-adapters-receive-argv-and-a-constrained-type.md) | Adapters receive argv and constrained types |
| [0006](adr/0006-the-static-router-escalates-rather-than-guesses.md) | The static router escalates rather than guesses |
| [0007](adr/0007-asserted-permissions-until-a-host-reports-them.md) | The user may assert a permission until a host reports it |
| [0008](adr/0008-applescript-values-travel-as-argv.md) | AppleScript values travel as argv; albums start at a track |
| [0009](adr/0009-the-model-is-configuration.md) | The model is configuration; the client is httpx |
| [0010](adr/0010-confidence-has-three-bands.md) | Confidence has three bands; the middle one asks |
| [0011](adr/0011-generated-text-is-content-typed.md) | Generated text is content-typed; a failed translation returns the original |
| [0012](adr/0012-what-the-evals-measured.md) | What the evals measured, and what changed because of it |
| [0013](adr/0013-qwen3-8b-is-the-default-model.md) | qwen3:8b is the default model |
