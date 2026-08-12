# CLAUDE.md

Instructions for Claude Code working in this repository. This file is
normative. When it conflicts with a request, say so before proceeding.

---

## What this is

E.V. is a local-first personal assistant for macOS.

**Goal:** turn spoken or typed intent into a small set of correct, fast,
auditable actions on this machine, with no data leaving it.

Four parts, four responsibilities:

| Part | Role |
|---|---|
| **Python core** | The brain and coordinator: routing, policy, registry, journal, confirmation |
| **Tauri 2 + Vue 3** | The application: menu bar, floating panel, settings, history |
| **Rust/Swift native host** | The nervous system: TCC-facing capabilities, audio, camera, NSPanel, global hotkeys |
| **Ollama** | Proposes intent and generates content. Never receives authority over the machine |

Three surfaces, one core: a CLI, a menu bar app, and a page served to this
machine's browser. None of them executes anything — they all speak to the core,
and the core owns the door.

Target hardware: Apple M2 Pro, 32 GB. One 7B–9B quantized model resident on
the interactive path. A larger model may exist for non-interactive work; it is
never the voice brain.

### Non-goals

E.V. is not a general agent. It does twenty things reliably rather than
anything unreliably. If a request implies unbounded control of the machine,
push back and propose a bounded adapter instead.

**Current phase: 1 (Ollama structured routing).** Phase 0 (headless core) is
done. Voice, native host and GUI are not built. Do not scaffold them unless
the task explicitly says so.

---

## Commands

```bash
make test           # pytest, must pass on Linux and macOS alike
make lint           # ruff + mypy
make eval           # golden routing evals, requires Ollama, NOT in CI
make models         # download model weights with checksum verification

python -m ev.cli "play the album Blonde"
python -m ev.cli --repl
python -m ev.cli --specs      # generated LLM tool specs
python -m ev.cli --manifest   # capability manifest
python -m ev.cli --macros     # saved macros, each step validated
```

`make test` must pass before any change is done. If a change makes the Python
suite require a real Mac, the change is wrong — that is what the fake binaries
in `tests/fakes/bin/` are for.

---

## Hard invariants

These are not preferences. Breaking one is a defect regardless of what it
enables.

### Model authority

1. **Raw model output never reaches a subprocess.** Tool arguments must be
   schema-validated with Pydantic, normalized, and passed to an allowlisted
   adapter.
2. **The adapter owns the executable, the permitted flags and the argument
   construction.** The model cannot choose an executable, a working directory,
   environment variables, redirections, arbitrary paths, or supply a complete
   shell or AppleScript program.
3. **There is no `run_shell(command: str)` tool.** There never will be.
4. **All tool execution goes through `Registry.call()`** and the permission
   policy. There is no second path.
5. **Destructive actions require explicit user confirmation** before execution,
   and the journal flush for them is urgent, not batched.

### Interface boundary

6. **No UI executes tools or invokes shell commands** — not the panel, not the
   browser page, not anything added later. A UI sends typed commands to the
   application core and only `Registry.call()` authorizes execution.
6a. **Every surface binds to this machine.** The IPC socket is a Unix socket;
   the web surface binds `127.0.0.1` and never `0.0.0.0`. E.V. acts on the
   machine it runs on, so reaching it from another one is not a feature to be
   secured — it is a different product.
7. **The signed native host owns TCC-facing capabilities**: microphone,
   camera, Accessibility, Apple Events. Permission state is reported to the
   Python core through typed events, never inferred.
8. **Camera and microphone require explicit permission and a visible
   active-state indicator.** Neither may be started by ambiguous model
   inference. Sessions have a timeout. Frames are not persisted by default.

### Data

9. **All inference, speech processing and stored data stay local.**
10. **E.V. makes no application-managed cloud API calls and sends no
    telemetry.** Explicit user actions may open internet resources in the
    user's browser. These two statements are not in conflict: the difference
    is who initiated it.
11. **SQLite is the only database.** WAL mode, FTS5, `sqlite-vec` only when
    retrieval actually lands. The database lives in
    `~/Library/Application Support/EV/`, never in the repository.

---

## The two model paths

Ollama serves two distinct flows. Conflating them dissolves invariant 1.

### Resolution path — routing

The model proposes an action. Its output is never shown to the user.

```python
class Resolution(BaseModel):
    tool: str
    arguments: dict[str, object]
    confidence: float
    response: str | None = None   # optional user-facing text
```

Flow:

```text
utterance
    ↓
static router (tier 0 learned phrases, tier 1 regex)
    ↓ unresolved
model router (tier 2, structured output against JSON Schema)
    ↓ Resolution
Pydantic validation against the tool's args model
    ↓
policy + confirmation
    ↓
Registry.call()
    ↓
adapter
    ↓
ToolResult
```

Below the confidence threshold, the resolution is refused or escalated to a
clarifying question. It is never executed on a guess.

### Generation path — content

The model produces text. Translation, summarisation, direct answers.

**Generated text may only enter a tool as a `content`-typed field. It may never
become a path, identifier, bundle id, executable, shortcut name, URL, or any
other argument that selects a target.**

"Translate this and save it to Notes" means the body is generated and the note
title is not.

---

## Language and translation

- **Detect the language of the request; answer in the same language** unless
  another is asked for.
- **The utterance reaches the router verbatim.** Language is a field on the
  session, not a transformation applied to the input.
- **Never translate as a preprocessing step before routing.** It adds a model
  round-trip to every turn, and proper nouns — album names, app names,
  playlist names — are precisely the tool arguments. A mistranslated argument
  is a failure that looks like a success.
- **Translation happens inside the generation that produces the response**
  where possible. Do not add a second call to translate what the first call
  could have written directly.
- **Never translate** code, URLs, file paths, identifiers, bundle ids,
  application names or structured tool arguments.
- **A translation failure returns the original text**, never guessed content.
- **Locale is `pt-PT`, not `pt-BR`.** Multilingual models default to Brazilian
  Portuguese. Carry `locale` in the session context, reinforce it in the system
  prompt, and — more importantly — write golden cases in pt-PT so the drift is
  measurable rather than assumed.
- **One model serves both paths.** A second resident model causes Ollama to
  swap, and the reload destroys the latency budget. Long `keep_alive`.
- **Golden routing cases exist in PT/EN pairs** for the same intent. Tool
  calling degrades in non-English; if the PT half fails consistently, the fix
  is a better model or more tier 1 coverage, not a translation shim.
- **Whisper runs with an explicit language hint, not auto-detect.** Auto-detect
  is unreliable on sub-two-second utterances, and short utterances are the
  normal case. Expect mixed-language input ("abre o Visual Studio Code") — this
  is why the model is `small`, not `base`.

---

## Architecture

```text
Tauri 2 / Vue 3          menu bar · NSPanel · settings · history
        │ Tauri commands
Native macOS host        TCC · signing · audio · camera · hotkeys
        │ Unix socket, typed JSON        ┌── browser (same Vue app)
Python core              assistant · router · policy · registry · journal
                         ▲ loopback HTTP, token, off by default ──┘
        │
Capabilities             browser · music · shortcuts · system · language
        │
Allowlisted adapters     AppleScript · Shortcuts CLI · open · native bridge
```

### Repository layout

```text
ev/
├── domain/              types shared across layers, no I/O
│   ├── results.py
│   ├── permissions.py
│   └── risk.py
├── application/         orchestration, no system access
│   ├── assistant.py
│   ├── confirmation.py
│   ├── policy.py
│   └── sessions.py
├── capabilities/        one directory per capability
│   ├── browser/
│   ├── music/
│   ├── shortcuts/
│   ├── system/
│   └── language/        generation path: translate, summarise
├── infrastructure/      the only code that touches the outside world
│   ├── database/
│   ├── macos/           applescript · accessibility · processes · shortcuts_cli
│   ├── ipc/             phase 1.5
│   └── ollama/          the single Ollama client, both paths consume it
├── router/
│   ├── static.py        tier 0 + tier 1
│   └── model.py         tier 2
├── registry.py
└── cli.py

tests/                   mirrors ev/, plus fakes/bin/
evals/                   golden routing cases, PT and EN
docs/
├── ARCHITECTURE.md
├── ROADMAP.md
└── adr/                 one file per architectural decision
native/                  phase 1.5+
ui/                      phase 3+
protocol/                phase 1.5
```

**Routing lives in `ev/router/` only.** There is no `application/routing.py`.
Two modules for one seam is one module too many.

### Capability anatomy

Every capability directory has the same four roles:

```text
args.py       Pydantic models. The single source of truth for the schema,
              for validation, and for the generated LLM tool spec.
tools.py      Registry entries. Declaration only, no logic.
service.py    Orchestration: permissions, confirmation, journal. Never
              touches the system directly.
adapters.py   The boundary. The only code here that talks to macOS.
```

`adapters.py` becomes `adapters/` only when there is a second adapter. Do not
create the package pre-emptively.

### One door per subsystem

Each subsystem has **one public port**. Multiple private modules may implement
it, but every external call passes through that port. This is a boundary rule,
not a single-file rule — it does not mean one giant module.

Only these classes touch the system directly:

```text
AppleScriptClient · ProcessRunner · AccessibilityClient
ShortcutsClient · NativeBridge
```

### Threads

**No application-managed threads in the Python core.** `asyncio` only.

This does not extend to the native layer: AVFoundation, Core Audio and the
Accessibility APIs use system-managed queues and callbacks. Forbidding them
there would force worse implementations.

### App control, in order of preference

1. **Scripting dictionary / AppleScript** — Music, Mail, Notes, Finder, Safari,
   Reminders. Use this whenever it exists.
2. **Accessibility API (`AXUIElement`)** — only through named adapters
   (`SlackAdapter`, `ChromeAdapter`). There is no `GenericAppController`.
3. **Synthetic keyboard/mouse events** — last resort. Fragile against
   resolution, language, window position, app version, animation and focus.
   **Never for destructive operations.**

---

## Recipes

### Adding a tool

1. Define the args model in `capabilities/<cap>/args.py`. Constrain the types —
   `HttpUrl`, `SafePath`, `Literal[...]`, not `str`.
2. Add the registry entry in `capabilities/<cap>/tools.py`, with risk level.
3. Implement orchestration in `service.py`.
4. Implement the system call in `adapters.py`, asserting on the exact argv or
   AppleScript source.
5. Add a fake binary case in `tests/fakes/bin/` if a new executable is involved.
6. Add a golden routing case in `evals/`, in **both** PT and EN.
7. Run `make test && make lint`.

### Adding a capability

Same as above, plus: create the directory only when the first tool lands in it.
**Do not create empty capability directories.** An empty `camera/` tells Claude
Code there is a contract to respect when no design decision has been made, and
invites code shaped by folder symmetry rather than analysis.

Future capabilities are described in `ev/capabilities/README.md`, not
scaffolded.

---

## Testing

- Assert on **exact argv and exact AppleScript source**, not on mock call
  counts. The thing that matters is what reaches the process boundary.
- Fake executables in `tests/fakes/bin/`, prepended to `PATH`. No mocking of
  `subprocess`.
- Routing has **golden cases**, not example-based tests. A routing change that
  moves a golden case is a decision, and shows up as a diff.
- Model evals are **not in CI**. They need weights and are non-deterministic.
  `make eval` locally; optionally a nightly that records the routing hit rate
  rather than failing a build.
- The Python suite runs on Linux. This is deliberate and is the fast feedback
  loop.

---

## Latency budget

Measured from push-to-talk release to first audio out. Every row says whether
it is a measurement or still a guess, because the two were indistinguishable
here until phase 1 and the guesses were wrong in both directions.

| Stage | Budget | State |
|---|---|---|
| STT (whisper small, ~2.5 s utterance, Metal) | 750 ms | **measured 723 ms** |
| Static router hit | 1 ms | **measured 0.005 ms** |
| Model router (8B q4 resident, ~24 tokens out) | 1.4 s | **measured 1.31 s** |
| Tool execution (AppleScript, no app target) | 100 ms | **measured 62 ms** |
| Tool execution (AppleScript, driving an app) | 300 ms | target, unmeasured |
| TTS first audio | 200 ms | target, not built |
| **Deterministic path, total** | **1.0 s** | TTS is the last target in it |
| **Model path, total** | **2.3 s** | router 1.31 s + STT 0.72 s |

Measured on an M2 Pro, `qwen3:8b`, model resident, 18 routing cases.
Reproduce with `make eval`; the per-stage numbers are in ADR 0012, 0013 and
0014.

**Half of STT is loading a model that is then discarded**: 362 ms of the
723 ms. Keeping whisper resident would halve it, and `CLAUDE.md` says not to
hold the LLM and the STT model resident at once — so spawning per utterance is
the intended design, and 723 ms is what it costs.

**A cold model costs more than the whole budget.** A reload measured 7.46 s
against 0.40 s warm, which is why `keep_alive` is 30 minutes and why a second
resident model is a decision rather than a detail.

Consequences that are already rules:

- Deterministic commands use the static router and never invoke Ollama. This is
  worth more than it looked: the real ratio is 0.005 ms against 1.31 s.
- Stream model responses where it shortens perceived latency.
- Do not add an LLM call that an existing call could have covered.
- Voice responses are concise by default, **and so is the router**: it fills
  `response` only to ask a question, never to narrate a tool call. Not doing so
  cost 0.75 s per turn (ADR 0014).
- Do not hold the LLM, STT model, vision model and neural TTS resident
  simultaneously. Load the vision model on capture, unload after.

The model path is over its original 1.8 s. What remains is generation, so the
levers are a smaller model or fewer output tokens; prompt size was measured and
is not one.

---

## IPC protocol (phase 1.5)

Transport: Unix domain socket at
`~/Library/Application Support/EV/ev.sock`, mode `0600`, newline-delimited
JSON. **The socket is the privileged channel and stays one.** It is reachable
by this user's processes and by nothing else — no port to find, no origin to
forge, nothing a web page can address.

The browser surface below is deliberately *not* this. It is a second, weaker
door with its own rules, and it does not replace the socket: the app and the
CLI keep using the socket, and the web surface is off unless asked for.

Two asymmetric message families, two schemas:

- **Commands** (native → Python): request/response, correlated by `id`.
  `utterance.submit`, `confirmation.respond`, `session.cancel`.
- **Events** (Python → native): push, no response.
  `transcription.partial`, `speech.requested`, `confirmation.required`,
  `tool.completed`, `state.changed`, `permission.changed`.

Schemas live in `protocol/` and are the single source of truth for three
languages. `protocol/generated/` **is committed**, and CI regenerates and fails
on any diff — otherwise the Python, Rust and TypeScript views drift.

---

## The local web surface

E.V. has three faces and one core: the CLI, the menu bar app, and a page in
this machine's browser. The page exists so E.V. is usable without building a
Rust app — the same panel, in a browser tab, on the machine it acts upon.

**It adds; it removes nothing.** The CLI and the app keep talking over the
socket and are unaffected by whether this is running. Nothing here is a
migration, and the socket does not become legacy: it stays the channel the
signed host uses, because it is the one a web page cannot address.

It is the weakest of the three doors and is written down as such. A Unix socket
cannot be addressed by a web page at all; a loopback port can be addressed by
every tab you have open, and a hostile page will try. These are not
suggestions:

- **Loopback only.** Bind `127.0.0.1`. Binding `0.0.0.0` is a defect, not a
  configuration.
- **Off by default.** It runs only when asked for (`--web`). A surface that
  exists by default is a surface an attacker can rely on existing.
- **A token on every request.** Generated per daemon run, stored `0600` beside
  the journal, never logged and never journalled. No token, no answer — not
  even a helpful error naming what would have worked.
- **`Host` and `Origin` are validated on every request**, and anything else is
  refused. This is what stops DNS rebinding turning "localhost only" into
  "any site you happened to visit".
- **No CORS.** The page is served by the same origin it talks to. There is no
  legitimate cross-origin caller.
- **The page executes nothing.** It posts commands; `Registry.call()`
  authorizes. Invariant 6 covers it exactly as it covers the panel.
- **Confirmation happens in the page**, as an event and an answer, and a
  question nobody answers is a decline — the same rule as the terminal and the
  socket.
- **The browser owns the microphone here.** `getUserMedia` asks in the
  browser's name, not E.V.'s, and the audio takes the same `audio.submit` path.
  The signed host remains the only TCC-facing capability holder; the page is
  not one, and must not pretend to be.

One UI, two shells: the same Vue application is served by the daemon and
embedded in the app, differing only in how it reaches the core — `fetch` in a
browser, Tauri commands in the panel.

The Tauri host spawns the Python daemon as a sidecar and owns its lifetime.
Handshake carries a protocol version; a mismatch refuses to start rather than
degrading silently.

Speech crosses this boundary as intent, not audio. Python emits:

```json
{ "type": "speech.requested", "text": "Playing Blonde by Frank Ocean",
  "voice": "pt-PT", "interrupt": false }
```

The native layer owns the audio device.

---

## Speech architecture

STT and TTS are **replaceable adapters**. The core depends on interfaces, never
on an engine:

```text
SpeechRecognizer · SpeechSynthesizer · AudioSession
```

- **STT:** `whisper.cpp`, model `small` multilingual. Apple's `SFSpeechRecognizer`
  is a fallback backend at most — on-device availability varies by language and
  accuracy is lower when forced local.
- **TTS:** macOS `say` during development, `AVSpeechSynthesizer` in the
  application.
- **Order:** push-to-talk first, VAD second, wake word last. Always-on
  listening introduces power draw, false positives, echo cancellation and
  privacy problems simultaneously.

**TransformerTTS is not part of the architecture.** It may be evaluated later
as an experimental `SpeechSynthesizer` adapter. It must not become a required
dependency, block the voice pipeline, or shape the interface.

No voice cloning and no custom TTS training before the end-to-end voice
pipeline is stable.

---

## Shortcuts

- **Running** shortcuts is supported: `shortcuts run "<name>"`. The name is
  resolved against the real list of installed shortcuts, never passed through
  freely.
- **Creating** shortcuts programmatically is not possible. `.shortcut` files
  are encrypted with no public format and there is no public creation API. Do
  not attempt a workaround.
- E.V.'s own JSON macro format is the answer: a named list of validated tool
  calls that E.V. can create, edit, validate, version, import, export and run
  without depending on a private format.

---

## Out of scope

Do not introduce, and push back if asked:

- LangChain or any agent framework. The registry is the framework.
- Electron, and any browser tab reachable from another machine. A local page
  served on loopback is a supported surface; a shipped web application is not.
- Nuxt, Astro, SSR. The UI is Vite + Vue 3 + Pinia, SPA — one application,
  embedded in the Tauri app and served by the daemon to a local browser.
- Chroma, Qdrant, pgvector. Retrieval is FTS5 + `sqlite-vec` in the same file.
- Models above ~9B on the interactive path.
- A generic app controller driven by Accessibility.
- Model weights, database files, journals, `.env`, signing certificates or
  provisioning profiles in the repository.

---

## Roadmap

`docs/ROADMAP.md` is authoritative. Summary:

| Phase | Scope | State |
|---|---|---|
| 0 | Headless core: registry, journal, migrations, tools, CLI | done |
| 1 | Ollama tier 2, structured output, evals, confidence policy, translation capability | done |
| 1.5 | Typed IPC protocol + signed native host skeleton | done |
| 2 | Push-to-talk, VAD, whisper.cpp, AVSpeechSynthesizer | done |
| 3 | Tauri, menu bar, NSPanel, settings, history, local web surface | current |
| 4 | JSON macros, more adapters, retrieval | |
| 5 | Camera and vision | |
| 6 | Wake word, continuous interaction | |

Camera comes after the UI exists because it needs the indicator and permission
surfaces. Wake word is last because it is the hardest part of the audio stack
and a global hotkey delivers most of the value.

Phase 1 seam: `StaticRouter.resolve()` returns `Resolution | None`. The model
router returns the same type, so `Assistant.handle()` gains one fallback branch
and nothing else changes.

---

## Definition of done

- `make test` and `make lint` pass
- New behaviour has a golden case or an adapter test
- New routing behaviour has golden cases in both PT and EN
- No invariant above was weakened
- Nothing was restructured ahead of its trigger in `docs/ARCHITECTURE.md`
- Latency budget respected on the turn path
- Any architectural decision taken is written to `docs/adr/` as one file,
  stating the decision, the alternatives rejected, and why