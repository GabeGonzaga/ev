# 0012 — What the evals measured, and what changed because of it

Status: accepted
Date: 2026-08-11

## Context

`make eval` exists to answer two questions with numbers instead of intuition:
where the confidence threshold belongs, and whether translation translates.
The first runs were against the two models installed on the development
machine. Neither is a shipping candidate — `qwen3:14b` is above the ~9B ceiling
for the interactive path, `translategemma:4b` is a translation model being
asked to route — so these are a ceiling and a floor rather than a verdict.

## What was measured

**Routing, 18 cases, PT and EN paired.**

| | qwen3:14b | translategemma:4b |
|---|---|---|
| tool correct | 18/18 | 10/18 |
| invented a tool when it should have declined | 0/8 | 8/8 |
| arguments the tool would accept | 9/10 | 15/18 |
| highest confidence on an invented call | — | 1.00 |
| lowest confidence on a correct call | 1.00 | 0.90 |
| seconds, median | 3.5 | 2.4 |

**Translation, 8 cases**, after the change below: 6/8 and 5/8 passing,
**0/8 silent failures** on both.

## What changed as a result

**Nothing about the thresholds.** The sweep says they cannot help. `qwen3:14b`
answered 1.00 on all 18 cases, correct and incorrect alike;
`translategemma:4b` rated an invented call 1.00 as well. On that data every
threshold from 0.0 to 0.9 behaves identically, and only 1.0 changes anything —
by refusing correct answers. Self-reported confidence carried close to zero
information in both directions.

**The browser tool's description now demands the scheme.** `qwen3:14b` routed
"I need to look at example.com/pricing in my browser" correctly and then wrote
the bare domain, which `HttpUrl` refuses — a correct routing dying as
`INVALID_ARGUMENTS`. One sentence in the field description moved
arguments-valid from 8/10 to 9/10; the pt-PT half of that pair still fails.

**Translation asks for the source language in the same call.** Both models
return the input unchanged on some inputs, and E.V. reported success, which is
undetectable from outside. `source` is now a required field of the same
structured response — no second round-trip — and text unchanged with
`source != to` is a failure carrying the original text. Silent failures went
from 2/8 and 2/8 to **0/8 and 0/8**.

## Alternatives rejected

**Tightening the thresholds because tier 2 is risky.** The data says the dial
is not connected to anything. Raising it would refuse correct answers and stop
none of the wrong ones, while creating the impression that confidence is
handled.

**Removing the confidence policy, since confidence proved uninformative.**
Cheap to keep and it costs nothing when every answer is 1.0. A model that does
express uncertainty is not hypothetical, and this is the band that would catch
it — the 0.5 and 0.6 observations in ADR 0010 came from one.

**Comparing input to output to detect an echo.** It flags the legitimate no-op,
where the text is already in the target language, as a failure. Asking the
model which language it read is one more field on a request already being made.

**Changing the prompt to stop the echoes.** Tried and measured: rewording the
"already in the target language" rule moved `qwen3:14b` from 2 echoes to 3 and
left `translategemma:4b` unchanged. Reverted. Detecting the failure worked
where instructing against it did not.

## Consequences

**The confidence policy is not the defence it looks like.** What actually
contains a wrong tier 2 answer is the tool enum, argument validation at the
door, the permission gate, and confirmation for anything destructive. This is
worth stating because the opposite belief is comfortable and wrong.

**Latency is over budget and this is the first measurement of it.** A median
routing call of 3.5 s against a 900 ms target, on a 14B. An 8B should roughly
halve it, which still misses. The budget in `CLAUDE.md` is a target to be
verified, and it has now been contradicted once; whether the answer is a
smaller model, a shorter prompt, or a revised budget is a decision that needs
the shipping model measured first.

**pt-PT drift is real and now visible.** `qwen3:14b` produced "Estou no trem
para o escritório" — Brazilian `trem`, not `comboio`. The eval flags it because
the case names the word it must not use.

**The numbers above are single runs of a non-deterministic process.** They are
strong enough to act on where the gap is large (8/8 inventions, 0/8 silent
failures) and not where it is one case wide. Nothing here is a build gate.
