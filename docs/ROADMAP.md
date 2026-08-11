# Roadmap

Authoritative. `CLAUDE.md` summarises this file; where they disagree, this one
is right.

| Phase | Scope | State |
|---|---|---|
| 0 | Headless core: registry, journal, migrations, tools, CLI | done |
| 1 | Ollama tier 2, structured output, evals, confidence policy, translation capability | current |
| 1.5 | Typed IPC protocol + signed native host skeleton | |
| 2 | Push-to-talk, VAD, whisper.cpp, AVSpeechSynthesizer | |
| 3 | Tauri, menu bar, NSPanel, settings, history | |
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
