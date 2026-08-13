# 0033 — Four levels, per application

**Status:** accepted
**Date:** 2026-08-13
**Phase:** 4

## Context

E.V. could reach three applications, each hard-wired into a capability: Music,
Notes, Reminders. The question that started this was "let it work with the
applications in my Applications folder", and `CLAUDE.md` has a firm answer to
the obvious reading of it — no generic app controller, no unbounded control,
push back and propose a bounded adapter instead.

The user's own framing was better than a list of adapters: E.V. should reach an
application *only as far as the person has allowed*, with levels from full
access down to none.

## Decision

**Four levels, set per application**, in `applications.json` beside the
journal:

| Level | What E.V. may do |
|---|---|
| `open` | Act without asking |
| `ask` | Act after a yes in whatever surface asked, every time |
| `verify` | Act after macOS verifies the owner |
| `blocked` | Nothing. It refuses and says which application, and how to change it |

**An application nobody has decided about is `ask`.** Not `open`, which would
act on something the user never considered. Not `blocked`, which would mean
nothing works until a file is edited — and a security control people have to
fight is one they turn off.

**The level and the tool's risk are both floors, and the stronger wins.**
Finder can be `open` — it is used constantly — and emptying the Trash still
needs verification, because what makes that dangerous is the tool, not the
application. A tool may also set its own floor, for what speaks to other people
in the user's name.

**The application is read from validated arguments**, so the level checked is
for the application that would actually be touched. `music.play` names Music
always; `applications.open` is told which, and resolves it against what is
installed before the policy sees it.

**A surface that cannot satisfy an assurance declines it.** A click in a panel
proves someone is at the machine; it does not prove who. Only the signed app
can raise macOS's own authentication, so the terminal and the browser page
refuse `verify` and say where it can be answered instead. Substituting a weaker
yes for a stronger one is the one failure the level exists to prevent, and it
is the kind that looks like it worked.

**`applications.open` and `applications.quit`**, resolved against
`/Applications`, `/System/Applications` and their Utilities folders. Quitting
goes through the scripting dictionary rather than a signal, because `quit` lets
an application put its own documents away, and the difference is somebody's
unsaved work. The name reaches AppleScript as `item 1 of argv` and is used as
`tell application theName` — a value, never an interpolation.

## What this is not

It is not a generic app controller. `applications.open` launches and
`applications.quit` quits; neither drives an application's interface, and
nothing here reads or types into one. Anything further is a named adapter with
its own decision, which is what `CLAUDE.md` asks for.

## A defect found while building it

The first ordering returned the permission verdict before the application's
level was consulted, so an application set to `ask` was waved through on the
first call whenever the TCC permission behind it happened to be undecided.
Asking to be let through to macOS is not a reason to skip asking the person.
The confirmation now comes first, and there is a test named after it.

## Alternatives rejected

**One global setting for "how careful to be".** The whole point is that
trusting E.V. with Music says nothing about trusting it with Mail.

**Levels keyed on bundle identifiers.** More precise and unreadable. The file
is meant to be opened and understood, and `"mail": "blocked"` is a sentence.

**Asking macOS which applications exist through a private API.** Reading the
Applications folders is what the Dock does, and it needs nothing.

**Remembering an answer automatically after one yes.** A yes to one action is
not a yes to a level. The panel will offer "always" explicitly (next), and
until it does, a level is set by hand or with `ev --app <name> <level>`.
