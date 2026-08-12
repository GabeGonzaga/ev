# 0031 — The app owns the core

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 3

## Context

`CLAUDE.md` has said from the beginning that "the Tauri host spawns the Python
daemon as a sidecar and owns its lifetime". It did not. The consequence was
recorded in `docs/ROADMAP.md` as a correction rather than fixed:

> the app bundle does **not** make Apple Events attributable to E.V.
> `music.play` runs in the daemon, which spawns `osascript`, so the TCC subject
> is whatever launched the daemon.

Launched from a terminal, the daemon's Apple Events belong to the terminal.
Every grant lands on iTerm, the prompts name iTerm, and E.V. — signed,
entitled, with a usage string macOS never shows — has an identity it never
uses.

## Decision

**The app starts the daemon, and macOS follows the process tree.** `osascript`
is a child of the daemon, which is a child of the app, so the responsible
process is `EV.app`. That is the entire point, and it needed no new protocol
and no new permission: only for the parent to be the right one.

**A daemon that is already answering is adopted, not replaced.** Two cores on
one socket cannot work, and someone running one in a terminal is doing it to
watch it. The check is a handshake rather than a file test: `ev.sock` outlives
a crash, and a stale one would otherwise stop the app from ever starting a
core.

**What the app started, the app stops — with SIGTERM.** The journal batches,
and the daemon flushes on that signal. `Child::kill()` is SIGKILL and would
take the last few turns of the trail with it, which is why this crate now
depends on `nix` for exactly one call: `libc::kill` is `unsafe`, and the crate
forbids that.

An adopted daemon is left running. It was not ours to end.

**The daemon is given a PATH.** This is the part that would have been found
the hard way. A GUI application's children inherit `/usr/bin:/bin:/usr/sbin:
/sbin` and nothing else — there is no shell in the chain to read a profile.
`open` and `osascript` live in `/usr/bin` and would have been found;
`whisper-cli` is Homebrew's and is spawned by name, so a daemon started from
the app could route and act and never hear a word. Homebrew's directories are
appended, not prepended, so a tool someone deliberately put earlier in PATH
stays the one that is found.

Verified by running the daemon under `env -i` with exactly that PATH: it binds
the socket, answers a turn, and stops cleanly on SIGTERM.

**Which interpreter: the project's own `.venv`, and no fallback.** A bare
`python3` under a GUI app's PATH is `/usr/bin/python3` — no dependencies, and a
failure several seconds later with an import error instead of immediately with
a sentence. If `.venv` is not there, the app says so and everything except the
core still works.

**Which repository: the one the app was built in**, from
`CARGO_MANIFEST_DIR` at compile time. Honestly a development answer, and the
one case that exists: the app is built in the repository it runs from.

## What this does not do

**It does not bundle Python.** A distributed E.V. needs a runtime inside the
app — PyInstaller, or a relocatable framework build — and that is a
distribution decision nobody has made. Signing, notarisation and a Homebrew
dependency chain all come with it. Today's E.V. is built by the person who
runs it.

**It is unproven on device**, like the rest of phase 3. The logic is tested,
the environment story is verified in a shell, and whether macOS names EV in the
Apple Events prompt is a thing only running the app can answer.

## Alternatives rejected

**A `launchd` agent for the daemon.** It survives logout and starts on boot,
which sounds like an improvement until you notice that launchd would then be
the responsible process — putting the attribution back where it was, with an
extra install step.

**Bundling the daemon as a Tauri `externalBin` sidecar.** That is the
mechanism, and it needs a single-file binary, which means bundling Python.
Same decision as above, deferred for the same reason.

**A `daemon.stop` command on the socket.** A clean shutdown without signals is
appealing, but it makes "end the core" something any client can ask for, and
SIGTERM already means exactly this and is already handled.
