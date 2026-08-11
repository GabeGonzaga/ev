# 0016 — The daemon, and not for the reason I gave

Status: accepted
Date: 2026-08-11

## Context

`CLAUDE.md` specifies a Unix socket daemon: `ev.sock` beside the journal, mode
`0600`, newline-delimited JSON, a versioned handshake, commands one way and
events the other.

Asked why it should be built, the first reason offered was the warm model: a
cold load measured 7.46 s against 0.40 s warm, so a core that dies with its UI
would pay that on every launch.

**That reason is wrong.** Model residency belongs to Ollama, which holds
weights for `keep_alive` regardless of which process asked. A daemon does not
keep the model warm; Ollama does, whether the caller is a daemon, a CLI
invocation, or three separate ones.

Measured after building it: a turn through the daemon took 0.258 s, the same
turn through a fresh local core took 0.272 s. Inside noise. The CLI client is
itself a Python process paying the same interpreter and import cost, so it
saves nothing worth naming.

## Decision

**Build it, for the reasons that survive.**

* **The native host needs something to talk to.** `CLAUDE.md` has the Tauri
  host spawning this as a sidecar; the socket is the contract it spawns.
* **Confirmation has to stop being `input()`.** A menu bar cannot answer a
  terminal prompt. Over IPC it is what it always had to be: an event out, a
  command back, and a turn blocked in between.
* **One core, several clients.** A CLI, a panel and a debug client can share a
  registry, a journal and a permission ledger rather than each opening the
  database.

**Turns are serialised** behind a lock. **Lines are not**: each is handled in
its own task.

**A signal stops it gracefully**, flushing the journal and unlinking the socket.

## Alternatives rejected

**Not building it, given the stated reason evaporated.** The reasons above are
enough on their own, and the alternative — the host talking to a core that only
exists as a library — means designing the confirmation round trip inside Rust
later, against a Python API that was never shaped for it.

**stdin/stdout pipes instead of a socket.** Genuinely simpler, and defensible
given the same document says the host owns the process lifetime: no socket
file, no mode bits, no stale-file cleanup, and nobody else on the machine can
connect. It was rejected because a pipe binds the core to exactly one parent,
and the CLI client — the thing that keeps this honest today — could not attach
at all. The tension in `CLAUDE.md` between "sidecar owned by the host" and "a
socket at a well-known path" is real; this resolves it toward the socket, and
the cost is the cleanup logic below.

**Handling lines in sequence, one at a time per connection.** This was written
first and was a deadlock: a turn awaiting a confirmation blocks the reader, so
the `confirmation.respond` that would release it can never be read, and the
turn ends when the timeout does. The tests caught it as two 120-second waits.

## Consequences

**A crashed daemon leaves a socket file.** Startup probes it: if something
answers, it refuses to start; if nothing does, the file was debris and is
unlinked. Without that, a crash would need manual cleanup before the next
launch.

**Socket paths have a length limit** — 104 bytes on macOS — and the kernel's
error names neither the limit nor the path. Startup checks it and says both.
`~/Library/Application Support/EV/ev.sock` is comfortably inside; a deeply
nested home directory would not be.

**Silence is not consent, again.** A client that disconnects mid-confirmation
gets a decline, as does one that never answers within the timeout, as does a
turn with no client bound at all. That is the third place this rule has been
implemented; it is the same rule each time.

**SIGTERM was losing the journal.** The first end-to-end run recorded one turn
out of two: the daemon was killed between the turn and the flush. Signals are
handled now, verified by running two turns, sending SIGTERM, and finding both
rows. A daemon that only flushes on Ctrl-C is a daemon that loses the audit
trail in production, where nothing sends Ctrl-C.
