# 0013 — qwen3:8b is the default model

Status: accepted
Date: 2026-08-11

## Context

Phase 1 shipped with `qwen3:8b` as the default in `models.json` — a guess, made
before anything could be measured. Both candidates were then pulled and run
through `make eval` back to back, on the same machine, under the same
conditions.

## What was measured

**Routing, 18 paired PT/EN cases.**

| | qwen3:8b | llama3.1:8b |
|---|---|---|
| tool correct | **17/18** | 14/18 |
| en / pt-PT | 9/9 · 8/9 | 7/9 · 7/9 |
| invented a tool when it should have declined | **0/8** | 2/8 |
| highest confidence on an invented call | — | 1.00 |
| arguments the tool accepts | **10/10** | 9/10 |
| seconds, median | 2.06 | 2.00 |

**Translation, 8 cases: 6/8 each.** One echo each, zero silent failures each,
one pt-BR leak each. Run to run, `llama3.1:8b` moved between 7/8 and 6/8 on
identical input, so the two are indistinguishable here.

## Decision

**`qwen3:8b` stays the default for both roles.** The guess was right, and now
it is a measurement.

**The roles are not split.** They could be — `models.json` supports it — and
the data gives no reason: translation is a tie. A split would buy nothing and
cost a weight swap per turn, measured at 7.46 s cold in ADR 0009.

**The thresholds still do not move.** `qwen3:8b` answered 1.00 on every correct
call; `llama3.1:8b` rated both of its invented calls 1.00. Third and fourth
models, same finding as ADR 0012.

## Alternatives rejected

**`llama3.1:8b`.** It failed the case that matters most: twice it answered a
question no tool could serve, both times routing to `language.translate`, both
times at confidence 1.00. That is a wrong action taken silently, and it is the
exact failure the whole design is arranged around. It also missed two routings
outright, returning null where a tool applied.

**Splitting the roles — `qwen3:8b` routing, `llama3.1:8b` generating.** The
reason to consider it was an early run where llama scored 7/8 on translation.
It was noise: the same cases gave 6/8 next time, matching qwen3.

**Treating the latency result as acceptable because it is close.** It is not
close. See below.

## Consequences

**The latency budget is contradicted, and this is now the second measurement
saying so.** `CLAUDE.md` allots 900 ms to the model router; the median is
**2.06 s**, and the whole model path is budgeted at 1.8 s. Both 8B candidates
sit at the same ~2 s, so this is not a model choice — it is the cost of a 5 GB
model on this machine. The options are a shorter system prompt (it currently
carries the full JSON Schema of every tool), a smaller model, or a budget that
says what is true. That is a decision, not a fix to slip in, and it wants the
prompt measured before the budget is rewritten.

**Tier 1 matters more than it looked.** Every static hit avoids ~2 s. The
deterministic path was justified by 5 ms versus 900 ms; the real ratio is 5 ms
versus 2000 ms.

**pt-PT is the weaker half for routing**, 8/9 against 9/9. The one miss is
worth reading: asked in Portuguese to play an album, `qwen3:8b` proposed
`browser.open_url` with an Apple Music link — to the **Brazilian** store
(`/br/`). Wrong tool, and the pt-BR drift `CLAUDE.md` warns about showing up in
routing rather than in prose.

**The eval instrument was wrong once, and was corrected.** `qwen3:8b`
translated "Bom dia" as "Good day", which the case counted as a miss because
the expected-wording list only held "good morning". The list was widened before
the comparison. A golden case that fails a correct answer is a bug in the
measurement, and worth more scepticism than a model that fails a case.
