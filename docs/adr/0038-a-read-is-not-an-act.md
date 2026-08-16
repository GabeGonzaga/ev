# 0038 — A read is not an act, and is not journalled

## Status

Accepted.

## Context

The music widget draws what is playing: track, artist, album, how far in,
whether shuffle and repeat are on, and the cover. To do that it asks once a
second while it is open.

Every call through `Registry.call()` is written to the journal. At one read a
second, a display left open for an evening writes some thirty thousand entries
saying that E.V. looked at the music player — and buries the entries that say
what E.V. *did*. The journal is what makes actions auditable; a log that is
99.9% status polls is not one.

The obvious alternative was to let the display read Music without going
through the registry at all, as `history.query` reads the journal. That is
worse: it would put a second path to an application beside the one door, and
it would step around the access level the user set for Music.

## Decision

`ToolSpec` gains `journalled: bool = True`. A tool sets it False only when the
call changes nothing on the machine. `music.now_playing` is the first.

Everything else is unchanged. The read goes through `Registry.call()`, the
arguments are validated, the permission is checked, and the application's
access level applies exactly as it does to `music.play` — reading Music is
still reaching into Music, and the level governs whether E.V. may. What is
skipped is one line: the journal entry.

## Consequences

The journal keeps meaning what it has always meant — what E.V. did to this
machine — rather than becoming a record of a display refreshing itself.

The flag is a small hole in "everything is recorded", so it is deliberately
narrow: a tool that writes anything, opens anything, sends anything or speaks
in the user's name is journalled, whatever its risk level. Anyone adding
`journalled=False` to a tool that acts is doing something the reviewer should
stop.

The user still authorises the read. Music is at `verify` on this machine, so
opening the widget asks for the owner once and that covers five minutes
(ADR 0035); the widget goes quiet, not stale-and-silent, when it expires. That
was the user's own choice when asked: reads take the same gate as everything
else.

## Alternatives rejected

**Exempt reads from the application level as well.** Cleaner for the widget --
it would never prompt -- and it was offered. Rejected by the user: nothing
should be read from an application without them having said yes.

**A dedicated IPC command outside the registry.** A second path to Music, with
its own policy story to keep in sync. One door is worth more than one line
saved.

**Poll less often.** It only moves the number. A widget that reads every five
seconds still writes seven hundred entries an hour, and the progress bar would
be a lie between reads.
