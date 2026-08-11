# 0008 — AppleScript values travel as argv, and albums start at a track

Status: accepted
Date: 2026-08-11

## Context

`music.play` is the first tool on the AppleScript route, which `CLAUDE.md`
makes the first preference for controlling applications. It is also the first
tool whose argument is an arbitrary user-supplied name — an album title — going
into a language where a stray quotation mark is a syntax boundary.

Music's own dictionary defines `play` as taking a single specifier: *"item to
play"*. It does not accept a list of tracks.

## Decision

**The script is a module-level constant, and values reach it as `argv`.**
`osascript -e '<constant>' -- <values>`, read inside with `item n of argv`.
Nothing is interpolated into the source.

**A test asserts the exact source and the exact argv**, with the expected
source written out literally rather than imported.

**An architecture test forbids adapters assembling strings at all** — no
f-string, no `%`, no `.format()`, `.join()` or `.replace()` in
`applescript.py` or any `capabilities/*/adapters.py`.

**`kind` is required, not defaulted.** `album` | `track` | `playlist`.

**An album starts at its first track and Music continues from there.** The
script prefers the track numbered 1, falling back to the first match.

**The spoken line reports the track it actually started on**, and the journal
records it.

## Alternatives rejected

**Escaping the name and interpolating it.** This is the normal approach and it
is a defect waiting for the right album title. Escaping AppleScript string
literals correctly means handling quotes, backslashes and the `¬` continuation
character, in a language whose grammar is not formally specified in public.
`argv` removes the question: there is no escaping to get right, because the
value never enters the program text. Verified against a name of
`" & do shell script "rm -rf ~" & "`, which arrives as a string.

**A temporary playlist, for exact album playback.** It is the only way to make
`play` traverse an album, and it mutates the user's library on every call —
creating and deleting a playlist as a side effect of "play Blonde". That is a
larger decision than this tool, and it was offered and declined.

**Track + playlist only, deferring albums.** Honest, and it leaves the marquee
example in `CLAUDE.md` unimplemented for a phase.

**Defaulting `kind` to `album`.** "Play Blonde" is ambiguous between an album
and a track, and a default resolves the ambiguity silently in favour of
whichever the author guessed. Required means the caller states it, and the
static router escalates rather than choosing (ADR 0006).

**Saying only "Playing Blonde".** The capability cannot make that claim: it
starts a track and lets Music continue in library order. Reporting the starting
track is the difference between a status and an assertion.

## Consequences

Album playback is approximate, and this is the known limitation of the tool.
Music continues in library order after the first track — usually the rest of
the album, not guaranteed, and it drifts onward at the end. Exact album
playback needs the temporary playlist above, which remains available as a later
decision.

`music.play` declares `APPLE_EVENTS`, so under ADR 0003 it is denied until the
user asserts the grant (ADR 0007) or a host reports it. A wrong assertion ends
at macOS, whose refusal — `Not authorized to send Apple events to Music` —
reaches the user as the failure message, because `AppleScriptClient` strips the
`execution error:` prefix and the numeric code and keeps the sentence.

`AppleScriptClient` is now the second port in the "one door per subsystem"
table, alongside `ProcessRunner`, and it goes through `ProcessRunner` rather
than around it.

The golden cases moved: `play the album Blonde` and `toca o álbum Blonde` were
`tool: null` in phase 0 and are now hits. That is the diff a routing decision is
supposed to produce.
