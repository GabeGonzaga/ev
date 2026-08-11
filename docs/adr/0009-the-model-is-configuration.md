# 0009 — The model is configuration, and the client is httpx

Status: accepted
Date: 2026-08-11

## Context

Phase 1 puts a model on the interactive path. Models are replaced far more
often than the code that calls them: a new version lands, a family turns out to
handle pt-PT better, two need comparing on the same golden cases.

None of the three models installed on this machine can serve routing —
`qwen3:14b` and `gemma3:12b` are above the ~9B ceiling `CLAUDE.md` sets for the
interactive path, and `translategemma:4b` is a translation model.

## Decision

**The model is named in `models.json`, per role, never in the code.** Roles are
`router` and `generation`; both default to one model, so nothing swaps.

**`--model NAME` repoints every role for one run**, which makes a bake-off a
loop rather than an edit.

**Different models per role are allowed.** The one-resident-model preference in
`CLAUDE.md` is a cost to accept knowingly, not something the code refuses.

**An unknown model fails with the installed list and the `ollama pull` line**,
read from `/api/tags`.

**httpx**, with `MockTransport` in the suite: no Ollama, no network, green on
CI Linux.

**Calls are not streamed, and `think` is off by default.**

## Alternatives rejected

**A constant, with the model chosen in code.** Every swap becomes a commit, and
comparing two models becomes editing between runs — which is how a comparison
stops being reproducible.

**Falling back to defaults when `models.json` is malformed.** E.V. would run a
model the user did not choose and cannot see. It raises with the path instead,
as the permission grants do.

**Stdlib HTTP over asyncio streams.** Zero dependencies, and it means writing
chunked transfer encoding by hand for the streaming the generation path will
want. The cost was real either way; httpx's `MockTransport` also buys hermetic
tests, which matters more here than the dependency count.

**The official `ollama` package.** It wraps httpx and adds vendor API churn on
top, for less control over `keep_alive`, timeouts and the exact structured
output payload — the three things this client exists to get right.

**Streaming the routing call.** A routing answer is ~60 tokens of JSON that
nothing can act on until it is complete. Streaming is for the generation path,
when something exists that can render a partial answer.

**Leaving `think` on.** Reasoning before answering costs multiples of the
budget on a call whose output is one small object. It stays available per role
for generation, where deliberation may earn its latency.

## Consequences

Measured against the running Ollama 0.31.1 while writing this: a cold load of a
4B model took **7.46 s**, the same model warm took **0.40 s**. The reload alone
is four times the entire model-path budget, which is why `keep_alive` defaults
to 30 minutes and why two models per turn is a decision rather than a detail.

`think: false` is accepted by models that do not support thinking, so it is
sent unconditionally rather than probed for.

Structured output is constrained during generation via `format`, and the result
is still validated: constrained decoding makes malformed JSON unlikely, not
impossible, and the schema is the router's rather than the tool's.

The suite gained no new external requirement. `make eval`, which needs real
weights, remains outside CI.
