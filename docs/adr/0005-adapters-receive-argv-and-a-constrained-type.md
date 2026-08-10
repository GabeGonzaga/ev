# 0005 — Adapters receive argv, and arguments are constrained types

Status: accepted
Date: 2026-08-10

## Context

`browser.open_url` is the first tool that reaches the system. It establishes
the shape every later adapter copies, so the constraints belong in the port and
in the args model rather than in each adapter's good intentions.

## Decision

**`ProcessRunner.run()` takes `Sequence[str]` and nothing else.** No shell, no
`cwd`, no `env`, no redirection — a caller cannot request them, so a tool
argument cannot become one. The executable is resolved on `PATH`.

**Arguments are constrained types, not `str`.** `OpenUrlArgs.url` is `HttpUrl`,
which admits http and https only.

**Every args model must set `extra="forbid"`; `Registry.register()` refuses
one that does not.**

**`TimeoutError` maps to `ToolErrorCode.TIMEOUT`, not `ADAPTER_FAILED`.**

**Adapters pass `--` before any value.** `["open", "--", url]`.

## Alternatives rejected

**A `str` URL, validated in the service.** `open(1)` dispatches every scheme an
installed application has registered — `file://`, `mailto:`, `x-apple-shortcuts://`,
anything a third party claimed. A tool named "open a URL in the browser" that
accepts `str` is really a tool for launching arbitrary local handlers, and the
gap only shows up when a model finds it. Putting the constraint in the type
means the generated LLM spec advertises the restriction and validation enforces
it, from one declaration.

**Hardcoding `/usr/bin/open` instead of resolving on `PATH`.** Marginally
tighter, and it makes `tests/fakes/bin/` impossible, which costs the suite its
ability to assert on real argv without mocking `subprocess`. The threat this
would address — a hostile `PATH` — is a compromise of the user account, at
which point the adapter is not the weak point.

**Allowing `env` or `cwd` on the runner "for later".** Every adapter that
genuinely needs them can be given its own method with its own fixed values. An
optional parameter on the shared door is a parameter something will eventually
thread model output into.

**Ignoring unknown fields, as Pydantic does by default.** A field the model
invented would pass validation, be dropped silently, and appear in the journal
as an argument that was never applied. Refusing at registration is cheap and
catches it at import time rather than at the first odd turn.

**Folding `TIMEOUT` into `ADAPTER_FAILED`.** They mean different things to the
user: a failure says the action did not happen, a timeout says E.V. stopped
waiting and does not know. Speaking the first when the second is true is worse
than saying nothing.

## Consequences

`ev/capabilities/browser/service.py` is thin — it composes a `ToolResult` and
the spoken line, nothing more — because `Registry.call()` owns permissions,
confirmation and journalling. `CLAUDE.md` describes `service.py` as holding
those; with invariant 4 in place, what it actually holds is capability-specific
orchestration, which for this tool is almost nothing. Capabilities that resolve
a name against the real world (shortcuts, music) will carry more.

The spoken line is the URL's host, not the URL. Full URLs are not something
anyone wants read aloud.

Golden routing cases for this tool are not in this step. There is no router yet;
they land with `ev/router/static.py`, in PT and EN, per the recipe in
`CLAUDE.md`.
