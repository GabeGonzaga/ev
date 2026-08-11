# Roadmap

Authoritative. `CLAUDE.md` summarises this file; where they disagree, this one
is right.

| Phase | Scope | State |
|---|---|---|
| 0 | Headless core: registry, journal, migrations, tools, CLI | done |
| 1 | Ollama tier 2, structured output, evals, confidence policy, translation capability | current |
| 1.5 | Typed IPC protocol + signed native host skeleton | done |
| 2 | Push-to-talk, VAD, whisper.cpp, AVSpeechSynthesizer | current |
| 3 | Tauri, menu bar, NSPanel, settings, history | current |
| 4 | JSON macros, more adapters, retrieval | |
| 5 | Camera and vision | |
| 6 | Wake word, continuous interaction | |

## Phase 0

Turn a typed utterance into one correct, auditable action, with the whole
chain testable on Linux.

| | |
|---|---|
| Skeleton, `make test` / `make lint` | done |
| `ev/domain/`: results, risk, permissions, resolution | done |
| `Registry.call()`, the single door | done |
| Permission policy | done |
| SQLite: WAL, migrations, journal | done |
| First capability end to end: `browser.open_url` | done |
| Static router, tier 0 and tier 1, golden cases in PT and EN | done |
| CLI: one-shot, `--repl`, `--specs`, `--manifest` | done |
| Asserted permissions, so AppleScript tools are reachable before the host exists | done |
| `music.play` over AppleScript | done |

Phase 0 is done: two capabilities, one of them through the permission gate and
the AppleScript port, with 167 tests that run on Linux.

Known limitation, recorded in ADR 0008: album playback starts at the album's
first track and lets Music continue in library order, because Music's `play`
takes a single item. Exact album playback needs a temporary playlist, which
mutates the library and remains a later decision.

## Phase 1

| | |
|---|---|
| Ollama client, model as configuration | done |
| Tier 2 routing with structured output | done |
| Confidence policy, wired into the turn | done |
| Translation capability | done |
| `make eval` and tier 2 golden cases | done |
| Model chosen by measurement, not guess | done |

The latency table in `CLAUDE.md` now records measurements rather than guesses,
and marks which rows are still targets. The model path is 2.0 s against an
original 1.8 s; the remaining gap is generation, so the levers are a smaller
model or fewer output tokens.

`make eval` has two specific jobs waiting for it, both from observed behaviour
rather than theory:

* The thresholds in `models.json` are defaults. A model has been seen inventing
  a call and rating it 0.6.
* A translation model returned its input unchanged and E.V. reported success.
  An echo is indistinguishable from a legitimate no-op without measurement, so
  evals must count it as a miss, in both directions, per model.

## Phase 1.5

| | |
|---|---|
| `protocol/`: message types, versioned handshake, committed JSON Schema | done |
| `ev/infrastructure/ipc/`: the Unix socket daemon, with the CLI as its client | done |
| Rust generation from the artifact, committed and CI-checked | done |
| TypeScript generation | with the UI, phase 3 |
| Signed native host skeleton | done |

## Phase 2

| | |
|---|---|
| `SpeechSynthesizer`, and the host speaking `speech.requested` | done |
| `audio.submit` at protocol 1.1, transcribed by the core | done |
| Audio capture in the host, 16 kHz mono | done |
| whisper.cpp behind `SpeechRecognizer`, with a language hint | done |
| Push-to-talk (a keypress; a hotkey needs phase 3) | done |
| VAD, energy-based and relative to the room | done |

Decided: STT runs in the Python core (ADR 0018). The host captures, because
the microphone is a TCC surface and TCC belongs to the signed process.

Nothing here has heard a real voice yet: capture was verified with an immediate
stop, transcription with synthesised speech. Whether 800 ms is the right pause
and four times the noise floor the right threshold are questions for the first
person who talks to it.

Audible gap, now that it speaks: tool responses are composed in English, so a
pt-PT voice reads English words. Locale-aware responses need session context,
which is not built.

## Phase 3

| | |
|---|---|
| Journal read API, `history.query` at protocol 1.2, `--history` | done |
| TypeScript generated from the schema, CI-checked | done |
| Tauri shell: menu bar, panel, four commands | done |
| History in the panel; settings beyond locale | partial |
| App bundle, signed, with entitlements and usage strings | done, unproven |

The bundle is the phase's real prize: launched from a shell the host borrows
the terminal's microphone grant (ADR 0019), and only a bundled app gets an
identity macOS decides about.

## What each phase is waiting for

**Phase 1** needs the tier 2 seam, which exists: `StaticRouter.resolve()`
returns `Resolution | None` and `Assistant.handle()` already branches on the
`None`. Tier 2 fills that branch. The confidence policy belongs here, not
earlier — nothing produces a confidence below 1.0 until a model does.

**Phase 1.5** is what makes permission state real. `PermissionLedger.update()`
is already the shape a `permission.changed` event feeds.

**Phase 5 (camera) comes after the UI** because it needs the indicator and
permission surfaces to exist first. **Phase 6 (wake word) is last** because it
is the hardest part of the audio stack and a global hotkey delivers most of the
value.
