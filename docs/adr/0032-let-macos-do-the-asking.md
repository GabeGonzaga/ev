# 0032 — Let macOS do the asking

**Status:** accepted
**Date:** 2026-08-13
**Phase:** 3

## Context

ADR 0003 denies on unknown permission state, and it was right to: in phase 0
nothing could report what macOS thought, and pretending otherwise would have
been a guess. `--grant` exists to work around it — the user asserts a
permission by hand so that E.V. stops refusing before the system is asked.

`ARCHITECTURE.md` listed `PolicyDecision.REQUEST_PERMISSION` as waiting for "a
native host that can service it". The host has existed since phase 1.5 and now
starts the daemon itself, so the trigger has fired.

The papercut is worth stating plainly, because it is what the change is for.
Testing the app meant running `ev --grant camera` before pressing Look —
telling E.V. something the machine already knew, so that E.V. would get out of
the way of a dialog only macOS can raise.

## Decision

**An undecided permission is not a refusal.** `UNDETERMINED` now yields
`REQUEST_PERMISSION`, which reaches the handler exactly as `ALLOW` does. E.V.
cannot put a TCC dialog on screen; only the attempt can. Standing in front of
the attempt does not protect anyone — it just means nobody is ever asked.

**A refusal is still a refusal.** `DENIED` denies, and says where to change it:
"System Settings > Privacy & Security > Automation". Retrying produces no
second dialog, only the same silent failure, so the pane name is the only
useful thing left to say.

**Permission before risk in the verdict**, so it reports the most specific true
thing about a call. A destructive tool is confirmed either way — `Registry.call()`
enforces invariant 5 itself, so a policy bug cannot let one run unasked.

**What the system answers is recorded.** Two sources, both evidence rather than
inference:

- *Apple Events*: the `AppleScriptClient` — the one door — reports `GRANTED`
  when an event is delivered and `DENIED` when macOS says "not authorized to
  send Apple events". A script that failed for its own reasons (a missing
  album, a syntax error) reports nothing, because it is not evidence about TCC.
  A delivered Apple Event is better proof than a person typing `--grant`.
- *Camera and microphone*: the host reports them over `permission.report`, new
  at protocol 1.5. Invariant 7 says permission state is reported by the signed
  host and never inferred by the core, and this is the mechanism it was
  describing. A frame that exists proves the camera opened; audio bytes prove
  the microphone did; the permission dialog's own answer is reported when the
  person gives it.

**Grants are written to `permissions.json`; refusals are not.** A grant learned
at runtime should be known on the next launch. A refusal on disk would outlive
the decision that caused it — TCC is changed in System Settings at any moment,
and E.V. would keep refusing something the user had since allowed.

`--grant` stays. It is now an assertion that saves the first attempt rather
than a requirement standing in front of every one.

## Alternatives rejected

**Polling macOS for permission state.** There is no supported way to ask about
Automation for a target application without sending an event, and for the
camera and microphone the answer belongs to the process that asked. Polling
would be inference dressed as a reading.

**Prompting the user in E.V.'s own UI first.** A second dialog in front of the
system's dialog, teaching people to click through two things instead of one.

**Recording denials permanently.** It makes the first refusal final, and the
recovery — "delete this file" — is worse than the disease.

**Treating any adapter failure as a denial.** A missing album would become a
permission problem, and a typo would silently disable a capability.
