# Architecture

What exists today, and what has to be true before each piece grows. `CLAUDE.md`
states the invariants; this file states the current shape and the triggers.

## Three surfaces, one door

```text
CLI ──────────────┐
menu bar app ─────┤  unix socket, 0600
browser page ─────┘  loopback HTTP, token, Origin checked, off by default
                          │
                     Registry.call()      the only thing that authorises
```

No surface executes anything. The web page is the weakest of the three and the
one written most carefully: a socket cannot be addressed by a tab, a port can,
so `ev/infrastructure/web/security.py` is what stands there and it is tested
against a real server rather than a fake.

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
| `protocol/` | domain | everything else |
| `native/` | the generated schema | the Python at all |
| `ev/application/` | domain | infrastructure, capabilities |
| `ev/router/` | domain | everything else |
| `ev/registry.py` | domain, application | infrastructure, capabilities |
| `ev/capabilities/` | domain, registry, infrastructure | other capabilities |
| `ev/infrastructure/` | domain, registry | application, capabilities, router |

`protocol/generated/` holds the same contract three times -- JSON Schema, Rust,
TypeScript -- generated from one Pydantic source and committed. Each toolchain
checks its own view (`make protocol-check`, `-rust`, `-typescript`), so none is
skipped quietly when its toolchain is absent.

`tests/test_architecture.py` enforces the parts of this that can be checked:
no outside-world imports above infrastructure, and no shell API anywhere.

Ports are declared by the consumer. `Registry` names `PolicyPort`,
`ConfirmationPort` and `JournalPort`; the application and infrastructure layers
satisfy them structurally, which is why neither imports the other.

## One door per subsystem

Each subsystem has one public port. Today there are seven:

| Port | Owns |
|---|---|
| `ProcessRunner` | every subprocess. argv only — no shell, no `cwd`, no `env` |
| `AppleScriptClient` | every AppleScript. Constant source, values as `argv` |
| `OllamaClient` | every model call, both paths. Local HTTP, model from config |
| `SpeechSynthesizer` | saying things. `say(1)` in development, the host in the app |
| `SpeechRecognizer` | hearing things. whisper.cpp, spawned per utterance |
| `IpcServer` | the socket. Handshake, framing, correlation, confirmations |
| `WebSurface` | the loopback page. Token, `Host` and `Origin`, off by default |

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
| Enforcing the `Content` marker | tools feed each other — macros, phase 4 |
| Streaming model responses | something can render a partial answer |
| `sqlite-vec`, FTS5 | retrieval actually lands (phase 4) |
| A model-based VAD | a measurement showing energy is not enough |
| A global hotkey (event tap, Accessibility) | phase 3, with the app bundle |
| `AudioSession` as a type | the host needs ducking, routes or interruptions |
| Camera, Accessibility in `native/` | phase 5 and later, one decision each |
| A second resident model | never on the interactive path |

## What does not exist yet

No wake word.

The voice loop closes: the host records on a keypress, the core transcribes and
routes, and the host speaks the answer. What it does not have is its own TCC
identity -- launched from a shell, macOS attributes the microphone request to
the terminal, and the host gets an identity of its own when it becomes a
bundled app (ADR 0019).

Tier 2, the generation path and `make eval` exist. `qwen3:8b` is the measured
default (ADR 0013): 17/18 routing, 0/8 inventions, 10/10 arguments accepted.

Two findings hold across four models. Self-reported confidence carries almost
no information — every model rates its wrong answers 1.00 as readily as its
right ones (ADR 0012). And **the model path is over budget**: 1.31 s median
against the 900 ms allotted to the router, after ADR 0014 stopped the router
narrating its calls. Every tier 1 hit is worth that 1.31 s.

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
- The Rust gate splits by what is portable. `make rust` builds and tests the
  host on both platforms, because its protocol client is plain Rust and that is
  where portability is worth proving. `make app-check` builds the app on macOS
  only: a menu bar, a panel, TCC and Apple Events are not portable, and
  building them on Linux would test GTK and WebKit instead.

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
| [0013](adr/0013-qwen3-8b-is-the-default-model.md) | qwen3:8b is the default model |\n| [0014](adr/0014-the-router-does-not-narrate.md) | The router does not narrate; the prompt was not the problem |
| [0015](adr/0015-the-protocol-is-authored-in-pydantic.md) | The protocol is authored in Pydantic and shipped as JSON Schema |
| [0016](adr/0016-the-daemon-and-why-not-for-the-reason-given.md) | The daemon, and not for the reason I gave |
| [0017](adr/0017-the-native-host-skeleton.md) | The native host skeleton, and what a second language found |
| [0018](adr/0018-where-speech-happens.md) | Where speech happens: capture is native, transcription is core |
| [0019](adr/0019-capture-in-the-host.md) | Capture in the host, and what the microphone actually asked |
| [0020](adr/0020-vad-is-energy-based-and-relative-to-the-room.md) | VAD is energy-based, and relative to the room |\n| [0021](adr/0021-the-app-is-the-tcc-subject.md) | The app is the TCC subject; the panel executes nothing |\n| [0022](adr/0022-a-local-web-surface-beside-the-socket.md) | A local web surface, beside the socket and not instead of it |
