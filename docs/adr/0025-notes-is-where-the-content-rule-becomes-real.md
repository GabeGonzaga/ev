# 0025 — Notes is where the content rule becomes real

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 4

## Context

`CLAUDE.md` states the generation-path rule with a worked example: "translate
this and save it to Notes" means the body is generated and the note title is
not. Until now the example had nowhere to land — `language.translate` has a
single `Content` field and no capability could take written text and put it
somewhere.

Notes is also the first capability that writes. Music plays and the browser
opens; both are undoable by looking away. A note persists.

## Decision

`notes.create(title, body, folder)`. `body` is `Content` and the other two are
not, which is the whole rule expressed as three type annotations. The marker
travels into the generated schema, so a checker — when tools start feeding each
other — can see which field accepts written text without knowing what Notes is.

`folder` is resolved against the folders that exist, using the same matching
`music.play` uses for playlists. That function moved to `ev/domain/naming.py`:
it is pure text, both capabilities need it, and two copies would drift.

An unknown folder is refused, not created. A folder invented from a mishearing
outlives the turn that made it.

The body is rendered to HTML in `ev/capabilities/notes/render.py` rather than in
`adapters.py`. An architecture test forbids adapters from assembling strings at
all, because an AppleScript source built by interpolation is one album name away
from being a program. That test is right, and the rule stays absolute: this
function builds a value that travels as `argv`, never a script, and it says so
where it lives.

The title is written twice — as the `name` property and as the body's first
line — because Notes shows the first line of a note as its title in the list. A
note whose title and first line disagree looks like a bug to the person reading
it.

`SENSITIVE`, not `DESTRUCTIVE`: it writes where the user can see it, overwrites
nothing and deletes nothing. A note that had to be approved before it could be
written would be slower than typing it.

### A golden case can now name the model's job

"Take a note called Boiler saying it was serviced in March" carries a title and
a body in one sentence. Tier 1 has no way to see where one ends, and a greedy
capture titles the note with the whole sentence — a wrong argument that looks
like a success. So the rule declines when the title contains a body or folder
clause.

That left an intent with no way to be written down: it is real, it should work,
and tier 1 must not answer it. Golden cases gained a `"tier": 2` field. The
suite asserts only that tier 1 stands aside; `make eval` measures the model
against the same tool and arguments. Previously a case was either tier 1's or
`null`, which said "nothing should route this" — a different and weaker claim.

## Alternatives rejected

**Creating the folder when it does not exist.** Convenient exactly once, and
then there are two folders differing by a space.

**Appending to an existing note.** It needs finding a note by spoken name,
which is the same matching problem with a much worse failure: appending to the
wrong note edits something that exists. Worth doing, worth doing separately.

**Letting the body carry HTML from the model.** The body is escaped. A model
that writes `<b>` meant the characters, and a capability that renders markup
written by a model is a capability that renders markup written by whatever
reached the model.
