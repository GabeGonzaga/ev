# 0006 — The static router escalates rather than guesses

Status: accepted
Date: 2026-08-10

## Context

Tier 0 and tier 1 answer without a model. Everything they answer costs
microseconds instead of ~900 ms, so the temptation is to make the patterns
greedy. The cost of a wrong tier 1 hit is not a missed shortcut, though — it is
a confident wrong action, taken without ever consulting the model that would
have known better.

## Decision

**`resolve()` returns `None` for anything it is not sure of.** `None` means
"not mine", not "no".

**A static hit is `confidence = 1.0`.** It is a lookup, not an estimate.

**Rules for every language are live simultaneously.** No language gate, no
detection step before routing.

**Matching is case-insensitive; captured arguments keep their case.**

**A pattern may decline after matching.** `Rule.build` returns `None` to mean
"this was not really a hit", and routing continues. A bare `report.pdf` uses
this: filename-shaped, so it escalates rather than becoming a URL.

**A scheme-less domain becomes `https://`, chosen by the router.**

**Learned phrases are injected, not read from disk.**

## Alternatives rejected

**Routing `open <anything>` to the browser and letting validation catch the
rest.** It looks free — `HttpUrl` rejects "Safari" and the user gets an error.
But the failure arrives as "invalid arguments" for an utterance the model
router would have understood, and every future non-browser "open" intent
(files, applications, notes) is now shadowed by a regex that claimed it first.
Escalating costs one model round-trip; a wrong hit costs the right answer.

**Detecting the language and selecting a rule set.** Adds a step before every
turn to decide something the patterns already encode, and it fails exactly on
the input this assistant expects — "abre o Visual Studio Code" is neither
language cleanly. Both sets are cheap to try.

**Lowercasing the utterance before matching.** Then "abre Blonde" routes with
`blonde`, and the argument reaching the adapter is not what the user said.
Album names, application names and paths are the arguments; case is theirs.

**Requiring an explicit scheme for URLs.** Correct, and unusable by voice:
nobody says "h-t-t-p-s colon slash slash". Since the router must supply one, it
supplies `https` — deterministically, in code, with the model nowhere near the
choice.

**A TLD allowlist instead of a file-suffix guard.** Precise, and it becomes a
list to maintain against a registry that keeps growing. The suffix guard is
small, targets the actual confusion (documents named like domains), and yields
to an explicit scheme.

**Loading `phrases.json` inside the router.** Routing is a pure decision and is
tested as one. Reading a file the user owns is the caller's job, and the file is
gitignored precisely because it is theirs.

## Consequences

Golden cases live in `evals/routing/*.jsonl`, one file per capability, and they
run in `make test` because they are deterministic. Tier 2 evals — weights,
non-determinism — remain `make eval` and out of CI.

`tool: null` cases are first-class: they assert that an utterance falls through
to the model router. Those are the cases that catch a pattern which grew too
greedy, and there are as many of them as there are hits.

A test fails if any intent lacks both a `pt-PT` and an `en` case. Tool calling
degrades in non-English, and pairing is what makes that measurable rather than
assumed.
