# 0027 — A due date is computed, so the router is told the time

**Status:** accepted
**Date:** 2026-08-12
**Phase:** 4

## Context

`reminders.create` is the first tool that takes a value the model has to
*derive*. Every argument before it was a name someone said — an album, a
playlist, a note's title — and `CLAUDE.md`'s rule for those is to copy them
verbatim, because a changed name is a wrong action that looks right.

"Amanhã às nove" is not in the utterance. It is a function of the utterance and
of what day it is, and the router did not know what day it was.

## Decision

**`due` is a `datetime`.** Pydantic parses it at the one door. A string would
have pushed the problem into AppleScript, and AppleScript's `date "13/08/2026"`
is parsed against the machine's own date format — the same source meaning
different days on two Macs. The script therefore never sees text: the adapter
sends year, month, day and seconds-since-midnight as integers, and the date is
built from `current date`.

The script sets the day to 1 before setting the year and the month. On the 31st
of January, setting the month to February gives the 3rd of March. The order
looks strange and is the fix.

**The router gets a second system message with the time.** After the tool list,
before the utterance. Two reasons for the separation: the tool list is byte-
identical every turn and Ollama caches that prefix, and a daemon that has been
up for two days would otherwise still be saying it is Monday. The utterance
itself stays verbatim — context goes in a system message, never as a prefix on
the user's own words.

**The format of that message was chosen by measurement, not by taste.** Six
utterances, qwen3:8b, each wording run against all of them:

| Context | "amanhã às nove" | "tomorrow at nine" | "daqui a duas horas" |
|---|---|---|---|
| none | — | — | — |
| `Today is Wednesday, 12 August 2026` | a day late | correct | a day late |
| `Now: 2026-08-12T19:45 (Wednesday). Tomorrow: 2026-08-13.` | correct | correct | correct |

The date written in the format the answer must use is worth more than any
wording. Tomorrow is spelled out rather than left as arithmetic, for the same
reason.

**A past due date is refused, with an hour of grace.** The way a model gets a
date wrong is to be confidently in the wrong year, and Reminders accepts that,
fires immediately and reports success. The grace exists because "remind me at
six" said at 18:02 is a real request. The refusal says the date back, so a
wrong year is visible rather than mysterious.

**`reminders.create` has no body field.** It had one — `notes`, `Content`, the
same shape `notes.create` uses. Measured, the model filled it with the request
it had just been given ("remind me to call the dentist tomorrow at nine" as the
body of a reminder titled "call the dentist"), and once with a word that was in
neither the request nor the reminder. Sharpening the description did not stop
it. A field a model reliably misuses does not belong in the schema; a reminder
is a line and a time, and `notes.create` is where written text goes.

**Tier 1 takes reminders with no date at all** — "lembra-me de comprar pão" —
and stands aside for anything with a time in it. A regex cannot compute a date,
and a greedy capture would set a reminder titled "comprar pão amanhã às nove".

## What this does not fix

"On the 1st", when the 1st has passed, resolves to this month rather than next.
A sentence spelling that rule out was tried and made it worse: the English case
went back to writing a date in the past. The service refuses past dates and
says so, which is the honest end of it. "Tomorrow", "tonight", "in two hours"
and "on the 20th" all measure correct, and those are the phrasings that matter.

## Alternatives rejected

**A relative schema — `{days: 1, hours: 9}`.** It moves the arithmetic into
E.V., which is appealing, and it makes every absolute date ("on the 20th",
"on Friday") a second encoding to design. The model computes absolute dates
correctly once it knows the time.

**Trusting the model and skipping the past check.** The check costs a
comparison and catches the one mistake models actually make with dates.

**Marking a reminder complete, or reading them back.** Both need matching an
existing reminder by spoken name, which is the same problem as appending to a
note: a wrong match edits something that exists. Separate decision, separate
adapter.
