# 0011 — Generated text is content-typed, and a failed translation returns the original

Status: accepted
Date: 2026-08-11

## Context

`language.translate` is the first tool on the generation path. It is also the
first place where text a model wrote becomes a value that could travel onwards
into another tool — which is the thing `CLAUDE.md` forbids: generated text may
only enter a tool as a `content`-typed field, never as a path, identifier,
bundle id, executable, shortcut name or URL.

## Decision

**`Content` is a type**, in `ev/domain/content.py`, and it carries a marker
(`x-ev-content`) into the generated JSON Schema. `TranslateArgs.text` is the
only field in the project declared with it.

**`to` is a `Literal`.** The target selects what happens, so it is a closed set
and can never be generated prose.

**A translation failure returns the original text**, in `data`, on a `ToolResult`
that is explicitly not ok. `ToolResult.failure()` gained a `data` argument for
this.

**The language capability has no `adapters.py`.** Its boundary is the model,
and the model already has a port.

**Tier 1 routes translation only when the text is quoted.**

## Alternatives rejected

**A plain `str` for `text`, with the rule left to reviewers.** The rule is
about provenance, which is invisible at the call site. A named type makes the
claim explicit in the one place it is true and absent everywhere else, and the
schema marker means a future macro engine can check it rather than trust it.

**Returning nothing, or an error alone, on failure.** The user's words are the
thing worth keeping. Reporting the failure and dropping the text loses input
E.V. was trusted with.

**Returning the original text as a success.** Convenient and dishonest: the
caller cannot tell a translation from an echo. `translated: false` is in the
data for exactly that reason.

**An `adapters.py` that forwards to the client.** Folder symmetry, one function
deep, with nothing to decide inside it.

**Routing unquoted translations in tier 1.** "translate good morning to
Portuguese" has no marker for where the text ends and the instruction resumes.
Guessing sends half a sentence to the model as though it were the whole of it,
so it escalates.

## Consequences

**Translation quality is the model's, and it is not visible from here.**
Measured against `translategemma:4b` while writing this: English→pt-PT produced
"Bom dia, como está?" — European, not Brazilian — and identifiers survived
("abrir o Safari e ir para github.com"). But pt-PT→English returned the source
unchanged, and E.V. reported success.

That echo is indistinguishable from the legitimate case the prompt allows for,
where the text is already in the target language. No heuristic here can
separate them honestly — comparing input to output would flag correct no-ops as
failures. So this is a measurement problem, and it belongs to `make eval`:
translation cases in both directions, per model, with the echo counted as a
miss. It is the second reason step 5 exists, alongside the confidence
thresholds.

The `Content` marker is not enforced yet, because nothing chains tools. When
macros land in phase 4, "the output of tool A may only enter tool B through a
`Content` field" becomes a check with a schema to read.
