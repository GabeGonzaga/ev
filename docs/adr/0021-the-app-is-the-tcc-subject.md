# 0021 — The app is the TCC subject, and the panel executes nothing

Status: accepted
Date: 2026-08-11

## Context

Phase 3 is Tauri, a menu bar, an NSPanel, settings and history. ADR 0019 found
that a binary launched from a shell borrows the terminal's microphone grant, so
the app bundle is what finally gives E.V. an identity macOS decides about.

## Decision

**`native/` is a workspace.** `host/` is the terminal client and a library;
`src-tauri/` is the app. The socket client and the capture code are shared by
path dependency rather than copied.

**Capture moved into the app.** TCC attributes a permission to the app, not to
a helper it launches, so the microphone has to be opened by the process the
grant is attached to.

**The window executes nothing.** The panel calls four Tauri commands —
`submit`, `listen`, `history`, `set_locale` — and the Rust side speaks the
protocol. No socket, no shell, no tool, exactly as `CLAUDE.md` requires of a
UI.

**The identifier is `com.gabegonzaga.ev`, and it is now frozen.** TCC keys
grants to identifier plus signing identity; changing either resets every grant
and re-asks every question.

**`LSUIElement`, and the close button hides.** A menu bar item, no Dock icon,
and quitting is a menu choice rather than an accident of clicking the wrong
corner.

**No app sandbox.** The entitlements ask for `device.audio-input` and
`automation.apple-events` under the hardened runtime, and deliberately not
`app-sandbox`: E.V. spawns `open`, `osascript` and `whisper-cli`, and the
sandbox forbids all three.

**The panel declines confirmations for now.** It has no way to ask yet, and an
app that answers on the user's behalf is worse than one that says no.

## Alternatives rejected

**Keeping capture in `ev-host` and letting the app launch it.** Simpler, and
the microphone grant would land on the wrong process — which is the exact
mistake ADR 0019 caught.

**`macOSPrivateApi` for a transparent panel.** It is one config key and a
private API, bought for a visual effect on a skeleton. An undecorated,
always-on-top window is the panel; vibrancy can be a decision when there is a
design to justify it.

**Letting the webview talk to the socket directly.** It would work, and it
would put execution one XSS away from the machine. The rule that the UI never
executes exists for exactly this shape of mistake.

**Bundling the Python daemon as a sidecar now.** `CLAUDE.md` describes it, and
it means packaging a Python runtime — a separate problem with its own failure
modes, and none of them are phase 3's subject.

## Consequences

The bundle exists, is signed with the hardened runtime, and carries the
entitlements and usage strings. Verified: identifier `com.gabegonzaga.ev`,
team `C7K67DZ94H`, `LSUIElement` true, both usage descriptions present, both
entitlements claimed.

**What is still unverified: whether macOS actually prompts.** Nobody has run
the bundle and clicked anything. The next microphone use from `EV.app` should
name E.V. rather than the terminal, and the first `music.play` should raise an
Apple Events prompt that turns ADR 0007's asserted permission into reported
state. Until someone runs it, that is a prediction.

The dependency footprint grew by a webview toolchain and 76 MB of
`node_modules`. `CLAUDE.md` names Vite, Vue 3 and Pinia as the intended stack,
so this is the shape it asked for; it is still the first tree in this project
nobody here has read.
