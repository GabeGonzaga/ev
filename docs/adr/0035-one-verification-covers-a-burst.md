# 0035 — One verification covers a burst

**Status:** accepted
**Date:** 2026-08-13
**Phase:** 4.5

## Context

`verify` worked on the first try, and the first real use said what was wrong
with it. Music was set to `verify`; the journal shows an album, a playlist,
another playlist and a pause, each one behind its own Touch ID prompt.

Two things were wrong, and only one of them is friction.

**A prompt for every action teaches people not to read prompts.** Playing an
album, skipping a track and pausing it are one intent. Asking three times
trains the exact reflex the prompt exists to interrupt: authenticate first,
read never.

**At `verify` there was no way to say "always".** The app answers those
questions with macOS directly and the panel never sees them, so the only offer
to change the level — the "Always allow" button — was unreachable for precisely
the applications that asked most.

## Decision

**A successful `owner` verification opens a five-minute window for that
application.** During it the level's own demand is satisfied and E.V. does not
ask again.

- *Five minutes* is `sudo`'s figure, and the ceiling macOS itself puts on
  reusing a recent Touch ID. Borrowed rather than invented.
- *A window, not a session*: it does not renew on use. A long afternoon of
  asking is a fresh prompt every five minutes, not one at the start of the day.
- *Per application*. Verifying for Music says nothing about Mail.
- *In memory only*. A window that survived a restart would be one nobody
  watched open.
- *Changing a level closes it.* A window opened under the old level says
  nothing about the new one.

**`owner_and_password` opens nothing.** The strongest level is for what cannot
be undone or what speaks to other people in the user's name, and "I did this
five minutes ago" is not a reason to skip asking about something irreversible.

**The window is opened by the surface that got the answer**, because only it
knows that the yes came from macOS rather than from a button. The policy is
what reads it.

**The terminal can say "always" and "never" too.** It could only ever say yes
or no, so the only way to stop being asked was to go and edit a file. The
prompt is now `[y]es / [n]o / [a]lways / ne[v]er` whenever an application is
named.

## Alternatives rejected

**Lowering Music to `open` and calling it solved.** That is the answer for
Music and not for the design: any application at `verify` had the same problem,
and the person would have found the same wall.

**Reusing the `LAContext` with `touchIDAuthenticationAllowableReuseDuration`.**
This is macOS's own mechanism for the same idea and it is tempting. It reuses a
*Touch ID*, not a decision: it would silently skip the password half of the
strongest level, it lives in the app rather than in the policy, and it is
invisible to `--apps`. The window is E.V.'s decision, so E.V. holds it.

**Making the window configurable now.** Five minutes with a reason beats a
setting nobody has an opinion about yet. It is one constant, named, in one
file.

**Renewing the window on each use.** That is a session, and a session that
renews is a session that never ends.
