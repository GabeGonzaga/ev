# 0003 — The permission policy denies on unknown permission state

Status: accepted
Date: 2026-08-10
Amends: [0002](0002-the-registry-owns-its-ports.md) — the policy port now
returns a verdict rather than a bare decision.

## Context

The policy reads two inputs: whether the TCC permissions a tool declares are
held, and how much damage the tool can do. Phase 0 has no native host, so
nothing reports permission state, and every permission is `UNDETERMINED`.

## Decision

**`UNDETERMINED` denies, exactly like `DENIED`.** A tool declaring a permission
cannot run until the host reports it granted.

**The policy port returns `PolicyVerdict` — decision plus reason.** The registry
surfaces the reason as the failure message.

**The risk threshold is a setting, `confirm_at`, defaulting to `DESTRUCTIVE`.**
At the default, `SENSITIVE` runs without a prompt.

**A withheld permission outranks the risk threshold.** Missing permission is
checked first and returns `DENY`, never `CONFIRM`.

**The policy reads a `Guarded` Protocol, not `ToolSpec`.** Read-only properties,
declared in `ev/application/policy.py`.

## Alternatives rejected

**Treating `UNDETERMINED` as "probably fine, try it".** The call would reach the
adapter and macOS would raise the TCC prompt as a side effect of an action the
user asked for by voice. That makes the permission dialog arrive with no
explanation of what triggered it, and it makes the Python core's model of the
machine depend on what the system happens to do — which invariant 7 exists to
prevent. Denying is the honest answer, and phase 1.5 replaces it with a real
request flow.

**A fourth decision, `REQUEST_PERMISSION`.** Correct eventually, useless now:
nothing can service it until the native host exists. Adding it in phase 0 would
mean a branch nobody can take and a contract shaped around an unwritten host.

**Confirming `SENSITIVE` by default.** Safer on paper, unusable in practice —
every `music.play` would prompt, on a voice path budgeted at 1.8 s. The
permission gate is what guards sensitive tools; the threshold exists for users
who disagree.

**Importing `ToolSpec` into the policy.** `ev/registry.py` already imports this
module for `PolicyDecision`, so that is an import cycle. The Protocol also
states precisely what the policy is allowed to read.

**A bare `PolicyDecision` return.** Produces "policy denied music.play", which
tells the user nothing. The reason is the difference between a refusal and an
explanation, and on the voice path it is the whole response.

## Consequences

`PermissionLedger` is mutable and owned by the application layer;
`permission.changed` events feed `update()` in phase 1.5. It defaults to empty,
so the deny-by-default behaviour needs no configuration.

Until the host exists, any tool declaring a permission is unreachable. The first
capabilities in step 6 must therefore declare permissions honestly rather than
conveniently — `open(1)` needs none, AppleScript needs `APPLE_EVENTS` — and the
AppleScript tools will be blocked by policy in phase 0. That is the correct
report of what this machine currently authorises.
