# 0022 — A local web surface, beside the socket and not instead of it

Status: accepted
Date: 2026-08-11
Amends: `CLAUDE.md`, which said "No HTTP, no localhost port".

## Context

E.V. had two surfaces: a CLI and a signed macOS app. Using it therefore meant
building a Rust application, which is a high price for someone who wants to
type a sentence at it. A page in this machine's browser removes that price.

The rule it contradicts was correct, and its reasoning still holds: *a port is
reachable by every process on the machine, including a browser tab*. Nothing
about wanting a web page makes that untrue.

## Decision

**Add the surface; keep everything.** The Unix socket stays the privileged
channel, the CLI and the app keep using it, and the web surface is a third
door that is **off unless asked for**. This is not a migration and the socket
is not legacy.

**The rule is replaced by stricter, more specific rules**, because a weaker
door with vague requirements is worse than no door:

* loopback only — binding `0.0.0.0` is a defect, not a setting
* a token per daemon run, `0600` beside the journal, never logged
* `Host` and `Origin` validated on every request
* no CORS
* the page executes nothing; `Registry.call()` authorizes, as for the panel
* an unanswered confirmation is a decline, as everywhere else

**Remote access is refused explicitly**, and invariant 6a now says why: E.V.
acts on the machine it runs on, so reaching it from another machine is not a
feature to secure — it is a different product with a different threat model.

**One Vue application, two shells.** Served by the daemon in a browser,
embedded in the app, differing only in how it reaches the core.

**The browser owns the microphone on that surface.** `getUserMedia` asks in the
browser's name; the signed host stays the only TCC-facing capability holder,
and the page must not pretend to be one.

## Alternatives rejected

**Serving the page over the existing Unix socket.** No browser can address a
Unix socket, so this is not an option, only a wish.

**Leaving the rule and shipping the page anyway.** The rule would then be a
lie in a normative document, which is worse than a rule that changed with a
reason attached.

**A shared or remote deployment.** Offered and declined: what would be shared
is control of a Mac — its apps, its Apple Events, its TCC grants — and no
permission model inside E.V. changes what the guest is holding.

**Leaving it on by default for convenience.** A surface that always exists is
one an attacker can count on. Off by default costs one flag.

## Consequences

**This is the weakest door E.V. has, and it is now the one to attack.** Today a
malicious page cannot reach the core at all, because there is nothing to
address. Afterwards, what stands between a hostile tab and this machine is a
token check and an `Origin` check being right. That is a real reduction in
safety, taken deliberately for reach, and it belongs in writing rather than in
a commit message.

The `CLAUDE.md` roadmap summary was three phases stale when this was written —
still marking phase 1 as current — and has been corrected. A normative document
that lies about where the project is will be trusted about something else next.

Nothing is implemented yet. This ADR records a decision about the shape of the
work, and the implementation follows.
