# 0002 — The registry owns its ports, and confirms destructive calls itself

Status: accepted
Date: 2026-08-10

## Context

`Registry.call()` is the single door (invariant 4) and the place destructive
actions are confirmed (invariant 5). To do that it needs a permission policy, a
confirmation surface and a journal — none of which it should implement, and two
of which do not exist yet at this point in phase 0.

## Decision

**The ports are Protocols defined in `ev/registry.py`, the consumer.** The
registry states what it needs; `ev/application/` and `ev/infrastructure/`
satisfy it structurally, without importing the registry or being imported by it.

**All three are constructor arguments, and none has a default.** A registry
cannot be built without a policy, a confirmation surface and a journal.

**A `DESTRUCTIVE` tool is confirmed whatever the policy answered.** The check is
`decision is CONFIRM or spec.risk is DESTRUCTIVE`, evaluated in the registry.

**A journal failure propagates.** It is not caught and discarded.

## Alternatives rejected

**Default no-op ports, so the registry is constructible alone.** Every default
here is a permissive one: a no-op policy allows, a no-op confirmation consents,
a no-op journal forgets. That turns "step 4 is not wired yet" into a silent
security downgrade rather than a `TypeError`. Tests supply fakes instead, which
is one line and makes the dependency visible in every test that has one.

**Ports declared in `ev/application/` and imported by the registry.** Puts the
interface with the implementation rather than the caller, so adding a second
implementation (the IPC confirmation surface in phase 1.5) edits the layer that
already had one.

**Letting the policy decide confirmation entirely.** It reads cleaner, and it
makes invariant 5 depend on a policy table being correct. Enforcing it at the
door means a policy bug degrades to an extra prompt, never to an unconfirmed
destructive action. The cost is one redundant condition, which is the point.

**Swallowing journal errors so a completed action still returns cleanly.** An
action that ran without being recorded is exactly the case the audit trail
exists for. Whether it retries, buffers or refuses is step 5's decision; until
then it fails loudly rather than quietly.

## Consequences

Unknown tools are refused but not journalled: nothing ran, and there is no tool
to attribute the record to. A router proposing a name that does not exist is a
routing failure, which `evals/` measures.

Handler results are re-attributed to the registered tool name before journalling,
so the audit trail cannot be shaped by an adapter returning the wrong name.

`CallRecord` carries validated, JSON-normalised arguments — except on
`INVALID_ARGUMENTS`, where the raw proposal is recorded, because that is what
was actually rejected. The journal's storage schema is not implied by this type;
step 5 maps it.
