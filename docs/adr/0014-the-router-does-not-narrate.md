# 0014 — The router does not narrate, and the prompt was not the problem

Status: accepted
Date: 2026-08-11

## Context

Two measurements said the model path was over budget: 3.5 s median on
`qwen3:14b`, 2.06 s on `qwen3:8b`, against the 900 ms `CLAUDE.md` allots to the
router. The obvious suspect was the system prompt, which carries the full JSON
Schema of every registered tool.

## What was measured

Five variants, 18 cases each, `qwen3:8b`, timings from Ollama's own counters.
The baseline was run twice to establish noise: 2.12 s and 2.15 s.

| variant | total | prompt eval | generation | out tokens | correct |
|---|---|---|---|---|---|
| baseline | 2.12s | 0.18s | 1.78s | 36 | 17/18 |
| baseline (repeat) | 2.15s | 0.18s | 1.81s | 36 | 17/18 |
| response null by default | 1.48s | 0.19s | 1.07s | 24 | 17/18 |
| lean specs + null response | 1.38s | 0.19s | 1.03s | 23 | 17/18 |
| no `response` field at all | 1.47s | 0.18s | 1.14s | 23 | 17/18 |

## Decision

**The prompt keeps its schemas.** Prompt evaluation costs 0.18 s whether the
prompt is 354 tokens or 556. Trimming it buys nothing measurable.

**The router does not narrate.** `response` must be null when a tool is being
called; it is written only when the model is unsure and needs to ask. Median
routing went from 2.06 s to **1.31 s**, with 17/18 correct, 0/8 inventions and
10/10 arguments accepted — unchanged.

**`response` stays in the schema.** Removing the field entirely measured no
faster than instructing the model not to fill it, and the field is what carries
a clarifying question in the language of the request (ADR 0010).

## Alternatives rejected

**Trimming the tool schemas to save prompt tokens.** The original hypothesis,
and wrong: a 200-token reduction moved prompt evaluation by 0.01 s. The 0.10 s
difference the lean variant showed is inside run-to-run noise, and dropping
`format`, `maxLength` and the rest risks the argument quality that a
description sentence was added to protect in ADR 0012.

**Blaming the client.** The eval reported 2.20 s where direct HTTP reported
1.50 s, which looked like per-call overhead — `OllamaClient` builds a new
`httpx.AsyncClient` for every request. Measured head to head on the same cases:
1.33 s through the client, 1.31 s through a reused raw connection. Client
construction costs 5 ms after the first. The 2.20 s reading was a cold model,
not our code, and the fix that suggested itself was not needed.

## Consequences

**Still over budget, by less.** 1.31 s against 900 ms. The remaining time is
generation — 24 output tokens of JSON — and the only lever left is a smaller
model or fewer output tokens, neither of which is free. The budget in
`CLAUDE.md` remains contradicted and remains a decision.

**A tier 1 hit now saves 1.3 s rather than 2 s.** Still three orders of
magnitude against 5 ms, so the tiering argument is unchanged.

**E.V. already had a rule that says this.** "Voice responses are concise by
default" is in the latency budget section; the router was paying for prose that
nothing displayed, because the tool result carries the spoken line.
