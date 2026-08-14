# Roadmap

Authoritative. `CLAUDE.md` summarises this file; where they disagree, this one
is right.

| Phase | Scope | State |
|---|---|---|
| 0 | Headless core: registry, journal, migrations, tools, CLI | done |
| 1 | Ollama tier 2, structured output, evals, confidence policy, translation capability | done |
| 1.5 | Typed IPC protocol + signed native host skeleton | done |
| 2 | Push-to-talk, VAD, whisper.cpp, AVSpeechSynthesizer | done |
| 3 | Tauri, menu bar, NSPanel, settings, history | done, unproven on device |
| 4 | JSON macros, more adapters, retrieval | done |
| 4.5 | Per-application access levels, launching and quitting | done, `verify` unproven on device |
| 5 | Camera and vision | done, unproven on device |
| 6 | Wake word, continuous interaction | the name is heard; the loop that listens is next |

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

First real use, and it went mostly well. Opening sites works on the phrasings
people actually use; the misses were transcription writing "github dot com" or
"github . com", which tier 1 now puts back together. Music was blocked by
E.V.'s own policy rather than by macOS -- no `permissions.json`, so it denied
before asking, exactly as ADR 0003 describes.

Correction worth carrying, now acted on: the app bundle does not by itself
make Apple Events attributable to E.V. `music.play` runs in the daemon, which
spawns `osascript`, so the TCC subject is whatever launched the daemon --
a terminal, until ADR 0031 made the app start it. Started from the app, the
responsible process is `EV.app`; started from a terminal and adopted, it is
still the terminal, and that is worth knowing when a prompt names the wrong
thing.

Closed: tool responses are composed in the language of the request. A phrasebook
per locale, looked up rather than generated, because these lines are written by
us and a model call to translate what we wrote would be a round trip for
nothing.

## Phase 3

| | |
|---|---|
| Journal read API, `history.query` at protocol 1.2, `--history` | done |
| TypeScript generated from the schema, CI-checked | done |
| Tauri shell: menu bar, panel, four commands | done |
| History in the panel, searchable | done |
| A global hotkey: hold to talk, anywhere | done, unproven on device |
| The app spawns the daemon and owns its lifetime | done |
| Permissions: macOS asked rather than pre-refused, answers recorded | done |
| Settings: the shortcut and the locale, remembered | done |
| Confirmation in the browser page, sharing the core's turn lock | done |
| Confirmation in the Tauri panel | done |
| Local web surface: loopback, token, `Origin` checked, off by default | done |
| The same Vue app served by the daemon and embedded in the app | done |
| App bundle, signed, with entitlements and usage strings | done, unproven |

Unproven means exactly that: `EV.app` builds, signs and verifies, and nobody
has yet held the key down on this machine and watched it hear something. The
parts it is made of are each exercised -- the socket, the capture, the
transcription, the turn -- but the app itself has not been run.

The bundle is the phase's real prize: launched from a shell the host borrows
the terminal's microphone grant (ADR 0019), and only a bundled app gets an
identity macOS decides about.

## Phase 5

| | |
|---|---|
| `vision.look`, with the frame bound per turn and never model-chosen | done |
| `vision.submit` at protocol 1.4, from a surface that captured a frame | done |
| The vision role: a larger model, loaded on capture and unloaded after | done |
| A frame in the browser: `getUserMedia`, one still, camera off again | done |
| Capture in the app: AVFoundation, an indicator, a session timeout | done, unproven on device |
| A frame from the screen rather than the camera | not decided |

Measured, gemma3:12b on an M2 Pro: 14-19 s from frame to answer, most of it
loading 8 GB of weights that are then dropped. That is the price of not
evicting the router, and it is why this is not on the voice path. A smaller
vision model is a line in `models.json`, which is the point of the role.

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
