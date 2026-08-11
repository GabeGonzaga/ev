# 0010 — Confidence has three bands, and the middle one asks

Status: accepted
Date: 2026-08-11

## Context

Tier 2 answers with a confidence it assigns to itself. That number is worth
something and is not worth trusting alone.

Twice while building this, a model asked "what is the capital of Portugal" —
something no registered tool can do — invented a `music.play` call rather than
returning null, and rated it **0.5**, then **0.6** on a later run. A single
threshold anywhere near the middle either executes that or refuses half of the
good answers.

## Decision

**Three bands.** At or above `accept_at` (0.7) the call runs. Below
`clarify_at` (0.4) it is refused as if nothing had been understood. Between
them E.V. asks.

**The thresholds live in `models.json`**, beside the model they judge.

**A clarification is its own type**, `Clarification`, carrying the tool, the
arguments and the confidence — not a `ToolResult`, because nothing ran.

**No wording lives in the domain.** `Clarification` carries the model's own
`response` when it gave one, since that is in the language of the request; the
CLI phrases the rest.

**An unreachable model is `EXIT_UNAVAILABLE` (4), never "I did not understand"**,
and a clarification is `EXIT_UNSURE` (3), never 2.

**Tier 2 runs only after tier 0 and tier 1 miss.**

## Alternatives rejected

**One threshold.** The observed numbers are the argument: an invented call at
0.5–0.6 and a correct one at 0.9 are separated by a band, not a line. A single
cut in that gap turns every near-miss into either a wrong action or a refusal,
and gives the user no way to correct a guess that was nearly right.

**Trusting the model's confidence alone.** It is self-assessment, and the two
observations here show it drifting upward on exactly the input it should have
declined. The band is a containment measure, not a measurement.

**Reusing the confirmation surface for low confidence.** Tempting — the
machinery exists. But confirmation answers "this is destructive, are you
sure?", and clarification answers "I might have misheard you". Conflating them
trains the user to accept both with the same reflex, which is precisely how a
destructive confirmation stops being read.

**Generating the clarifying question with a second model call.** A better
sentence, and another round-trip on a turn that has already spent one, for a
question whose content is entirely known: the tool, the arguments and how sure
E.V. is.

**Executing the middle band with a confirmation prompt instead of a question.**
Same mistake in a different order: it presents a guess as a decision to approve
rather than a hearing to correct.

## Consequences

The defaults are defaults, not findings. `make eval` is what moves them, and it
now has a specific job: measure how often a correct routing sits below 0.7 and
how often an invented one sits above it, per model and per locale.

The English fallback question is a known gap. `Clarification` carries the
model's own line when it exists, so a pt-PT request usually gets a pt-PT
sentence; the fallback wording is English until the language capability lands.

A clarification is not journalled, because nothing ran. What the model proposed
and was not trusted with is therefore invisible to the trail — the argument for
recording routing attempts separately from actions, which is a decision for
when something needs to read them.
