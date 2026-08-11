# 0007 — The user may assert a permission until a host can report it

Status: accepted
Date: 2026-08-11
Relates to: [0003](0003-the-permission-policy.md)

## Context

ADR 0003 denies any tool declaring a TCC permission while the ledger reports
`UNDETERMINED`, and phase 0 has no native host to report anything else. The
consequence is that every AppleScript tool — Music, Notes, Mail, Finder, the
whole first-preference route in `CLAUDE.md` — is unreachable until phase 1.5.

Deferring them means phase 0 ships one capability that needs no permission and
leaves the entire guarded path unexercised until a signed host exists.

## Decision

**The user may state, explicitly, that they have granted a permission.**
`python -m ev.cli --grant apple_events` records it in `permissions.json` beside
the journal; `--revoke` undoes it. `PermissionLedger` is seeded from that file
at startup.

**The wording is not "grant".** The command prints, every time, that it grants
nothing: macOS still prompts and can still refuse. It only stops E.V. refusing
first.

**An unknown permission name is an error**, in the file and on the command
line, and the error lists the known ones.

**The file lives beside the journal**, in E.V.'s state directory, and is
gitignored.

## Alternatives rejected

**Waiting for phase 1.5.** Correct, and it leaves the guarded path — policy,
confirmation, AppleScript adapter, exact-source assertions — untested against a
real tool for an entire phase. The parts most worth getting wrong slowly are
the parts this would defer.

**Treating `UNDETERMINED` as permissive after all.** This is the tempting
shortcut, and it is the one ADR 0003 exists to refuse. It would let macOS raise
a TCC dialog as a side effect of a voice command, with nothing on screen
explaining what asked for it.

**An environment variable.** Convenient, invisible, and easy to inherit from a
shell nobody remembers configuring. A file the user can read, diff and delete is
a better record of a claim about their own machine.

**Inferring the grant by trying the call and watching for error -1743.** That is
inference, which invariant 7 forbids, and it learns by triggering the very
prompt the deny-by-default rule exists to avoid.

**Silently ignoring unknown names in the file.** The user would believe they had
asserted something they had not, and would meet the contradiction much later as
a denial with no obvious cause.

## Consequences

This does not weaken invariant 7. The invariant forbids E.V. *inferring*
permission state; this is the user stating it, in their own words, in a file
they own. When the host lands it reports the real state through
`PermissionLedger.update()`, and this file becomes the fallback for a host that
is not running.

A wrong assertion is not dangerous, only wrong: the call reaches macOS, macOS
refuses it, and the failure surfaces as `ADAPTER_FAILED` with the system's own
message. Enforcement was never E.V.'s to perform.

`music.play` over AppleScript is now buildable and testable end to end, which
is the row after this one in the roadmap.
