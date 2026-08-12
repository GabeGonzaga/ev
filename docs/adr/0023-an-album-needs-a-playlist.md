# 0023 — An album needs a playlist, and music needs its buttons

Status: accepted
Date: 2026-08-12
Supersedes the album decision in [0008](0008-applescript-values-travel-as-argv.md).

## Context

ADR 0008 recorded three ways to play an album, since Music's `play` takes a
single item and not a list. The option chosen was to play the album's first
track and let Music continue from there, with its cost written down: *"says
'Playing Blonde' while possibly playing something else"*.

First real use: it played the first song and stopped. The approximation did not
approximate.

`music.play` was also the only music tool. Every button on a music app --
pause, skip, back, volume -- had no equivalent, so the only way to pause E.V.
was to open Music.

## Decision

**An album is played as a playlist.** E.V. keeps exactly one of its own,
`E.V. queue`, deletes and rebuilds it per album, and plays that. A playlist is
the only thing Music will play through.

**The queue is visible in the sidebar, on purpose.** A program that edits your
library should do so where you can see it, under a name that says who made it.

**Transport controls exist**: `music.control` with a closed set — pause,
resume, next, previous, stop — and `music.volume`, 0 to 100, Music's own
volume rather than the system's.

**A spoken playlist name is resolved against the playlists that exist.** Exact
first, then punctuation-blind, then a unique prefix or containment; ambiguity
matches nothing and the refusal names what is there.

## Alternatives rejected

**Keeping the first-track approximation.** It was tested and it failed. Its
own ADR predicted the failure mode.

**Not creating a playlist, to avoid touching the library.** The reason it was
rejected in 0008 -- that it mutates the library -- is real, and the measured
alternative is an assistant that cannot play an album. One named playlist,
replaced on demand, is a smaller cost than the feature not working.

**Matching playlists by exact name.** This library contains `{Jazzy}`,
`GO w/Flow!!`, `Indie kid??` and `Main PlayList :D`. Nobody dictates the
braces, and exact matching means the feature exists only for people who name
playlists like filenames.

**Guessing between two plausible playlists.** Playing the wrong one is worse
than saying which matched. Ambiguity returns nothing, and the message lists
what is there.

**One tool per button.** `music.control` with an enum keeps the tool count
honest: five names for five verbs on the same object would make the manifest
longer without making anything clearer.

**A name that is not an album, but is a playlist, plays.** Reported straight
after the controls landed: `toca ... Indie kid` answered "nothing in the
library matches Indie Kid" while `Indie kid??` sat in the sidebar. Nothing in
the library has that album, so there is no second reading to guess between --
one playlist matches and nothing else does. It plays, and it says so:
*"No album called Indie Kid. Playing the playlist Indie kid??"*. A wrong guess
should be audible rather than silent.

The fallback is narrow on purpose. Two plausible playlists is a guess and is
refused. And it only triggers on "nothing in the library matches": a refused
Apple Event is a permission problem, not a missing album, and must not be
turned into playing something else.

## Consequences

`E.V. queue` appears in the user's sidebar the first time an album is played,
and its contents change without warning. That is the visible price of album
playback, and it is stated here rather than discovered.

The controls need `apple_events` like everything else in this capability, so
they are denied until granted -- and the refusal now names the command that
grants it.

Six AppleScript sources now exist where there was one. All are constants, all
take their values through `argv`, and all compile against Music's dictionary.
The architecture test that forbids assembling strings in an adapter covers them
unchanged.
