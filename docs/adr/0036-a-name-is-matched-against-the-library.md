# 0036 — A name is matched against the library

**Status:** accepted
**Date:** 2026-08-13
**Phase:** 4

## Context

"Albums and artists in my library should be recognised, and it didn't." Three
separate defects wearing one complaint, all of them visible only against a real
library of 4229 tracks.

**Artists were not a thing.** `kind` was album, track or playlist. There was no
way to ask for an artist at all.

**Album names were matched exactly.** `every track whose album is theName`. The
library calls it `21st Century Breakdown (Deluxe Edition)`, `Abbey Road (2019
Mix)`, `÷ (Deluxe)`. Nobody says the parenthesis, so nothing matched.

**Ambiguity was refused too eagerly.** `closest` returned nothing when more
than one name matched. "Kendrick" matches six artists — `Kendrick Lamar` and
five collaborations crediting him — so it refused. Nobody asking for Kendrick
means `Future, Metro Boomin & Kendrick Lamar`.

## Decision

**The library is listed and the spoken name is matched against it**, the same
rule playlists, shortcuts and applications already follow. Albums first, then
artists, then playlists — the order people mean them — and whatever is found is
said out loud, so a wrong guess is audible rather than silent.

Listing costs one Apple Event and 0.24 s for 4229 tracks, and it happens only
when an exact match failed. The happy path is untouched.

**The shortest prefix wins, but only when it begins every other match.**
`Kendrick Lamar` starts `Kendrick Lamar & SZA`, so they are one artist said at
two lengths. `Jazz Classics` and `Jazz Nights` are two playlists, and taking
the shorter would be choosing by coin toss — that still refuses.

**Artists play everything they are credited on.** `artist contains theName`
rather than `is`: half of what an artist recorded is a collaboration, and the
name is resolved to the library's own spelling before it gets there, so
`contains` is matching a real artist rather than a fragment somebody said.

**The kind is a hint, not a contract.** "Play the album Kendrick" is a
reasonable thing to say and the wrong kind. A name that matches nothing of the
kind asked for is looked for among the others before E.V. gives up.

## Two bugs the real library found

**`duplicate matches to theQueue` fails on a long list.** Music answers "Can't
set user playlist id … to {shared track id …}" — found by asking for Kendrick
Lamar, whose 112 tracks were too many for one statement. Duplicating one track
at a time works, at about 19 ms each. That sets the bound: 500 tracks is 9
seconds against a 20-second timeout, so the queue stops there.

**`name of current track` right after `play` can fail.** The player has been
told to start and has not got there yet, so it has no current track and
AppleScript raises. This is ADR 0023 for the third time: the script compiled,
and only running it said otherwise. Every script that reports what is playing
now goes through one `my nowPlaying()` handler with a `try` in it.

Also found, by running `make applescript`: the runtime checker still called
the reminders adapter with an argument removed two ADRs ago. It is not in CI —
it needs a Mac with Music, Notes and Reminders — so nothing else could have
caught it.

## Alternatives rejected

**Edit distance for mis-transcriptions.** "indy kit" for `Indie kid??` is not
reachable by prefix or containment, and `difflib` at a cutoff loose enough to
catch it also matched things nobody said. A wrong album playing confidently is
worse than being told nothing matched.

**Listing the library on every play.** 0.24 s on every "pause", for a lookup
only needed when an exact match failed.

**Caching the listing.** A library changes while E.V. is running, and a cache
of it is a bug that appears the day someone adds an album and E.V. says it does
not exist. If listing ever becomes slow, it can be cached against Music's own
modification date — not before.
