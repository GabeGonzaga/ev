# 0028 — Hold a key, not an event tap

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 3

## Context

Phase 2 built push-to-talk and left the key itself for phase 3: a keypress in a
terminal is not a way to talk to a menu bar app. `ARCHITECTURE.md` listed the
global hotkey with "(event tap, Accessibility)" beside it, which turned out to
be a guess about the implementation and the wrong one.

## Decision

**One key combination, registered as a hotkey.** `tauri-plugin-global-shortcut`
sits on Carbon's `RegisterEventHotKey`, which delivers exactly the combination
that was registered and nothing else. E.V. therefore does not ask for
Accessibility to be listened to.

That matters more than the code it saves. An event tap can read every keystroke
on the machine, which is why macOS gates it behind Accessibility, and asking for
it to hear one chord would be asking for far more than the feature needs. The
cost is that a bare modifier — hold Fn, hold right-Cmd — is not available,
because a hotkey needs a key. That is a fair trade and it is written here so
that "just use an event tap" is a decision someone has to make again rather
than a convenience someone reaches for.

**Hold, not tap.** Key down opens the panel and starts recording; key up ends
it. The VAD path still exists behind the Speak button — this is `CLAUDE.md`'s
order, push-to-talk first and VAD second — and a held key is the more reliable
of the two, because it does not have to guess when a sentence ended.

Three bounds, each for a failure that actually happens:

- **Shorter than 250 ms is a tap**, and a tap only opens the panel. whisper
  given a fifth of a second of room noise returns whatever it hallucinates
  from it, confidently.
- **Longer than 30 s stops anyway.** A stuck key, an app that swallows the
  key-up, a lid closing mid-sentence: any of them would otherwise hold the
  microphone open until the app quit.
- **A repeat is not a second press.** A held key repeats; the recording slot is
  occupied, so the repeats are ignored.

**The result travels as an event.** The panel did not ask for this turn and
cannot await it, so `turn.started`, `turn.completed` and `turn.cancelled` are
pushed to the window. Everything else about the turn is identical to a typed
one: the same socket, the same lock in the core, the same confirmation, the
same journal.

**The shortcut is a setting**, stored in `~/Library/Application Support/EV/
app.json` beside the journal — not in the database, because an app that needs
the daemon running before it knows how to be summoned cannot be summoned to
start one. Rebinding registers the new combination before forgetting the old,
and writes the file only if that worked: a combination another application owns
must leave the working one in place rather than leaving E.V. with none. A
shortcut that will not bind at startup is printed and the app starts anyway.

## A bug this uncovered

The Tauri capability file granted `core:default` to a window called `main`. The
only window is called `panel`. Nothing in the app had been run yet, so it had
never failed — but `core:event`'s listen is in that set, which is how the panel
receives `confirmation.required`. The confirmation flow in the app would have
been dead on arrival.

## Alternatives rejected

**An event tap, for a modifier-only gesture.** Accessibility is a permission
that reads every keystroke. Not for this.

**Tap to start, VAD to end.** It exists, as the Speak button. As the global
gesture it is worse: the moment to stop is a guess, and the guess is made in a
room the app cannot see.

**Storing the shortcut in the journal database.** The database belongs to the
core. The app is a client of it, and a client whose own settings depend on the
service being up is a client that cannot start the service.
