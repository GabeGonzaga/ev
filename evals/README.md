# Golden routing cases

One JSONL file per capability, one case per line. These are goldens, not
examples: a routing change that moves a case shows up as a diff and is a
decision someone made, not a surprise.

```json
{"id": "open-url-bare-domain", "locale": "en", "utterance": "open github.com",
 "tool": "browser.open_url", "arguments": {"url": "https://github.com"}}
```

| Field | Meaning |
|---|---|
| `id` | The intent. Every id must exist in **both** `en` and `pt-PT`. |
| `locale` | `en` or `pt-PT`. `pt-PT`, never `pt-BR`. |
| `utterance` | Verbatim, as the user would say it. Not normalised. |
| `tool` | The expected tool, or `null` for "the static router must not answer". |
| `arguments` | What the router produces, **before** the args model validates it. |

`tool: null` cases are as important as the hits. They are the utterances that
must fall through to the model router rather than being answered by a regex
that happened to fit.

Cases in `routing/` are deterministic and run in `make test`.

## Model evals — `make eval`

Not in CI: they need weights and are not deterministic.

    make eval                                    # the configured model
    make eval ARGS='--model qwen3:8b --model llama3.1:8b'
    make eval ARGS='--only translation'

| Directory | Measures |
|---|---|
| `model/routing.jsonl` | tier 2: does it pick the right tool, decline when it should, and produce arguments the tool accepts |
| `translation/cases.jsonl` | does it translate, keep identifiers, and stay in pt-PT rather than drifting to pt-BR |

Two columns are worth reading before the totals:

* **invented a tool** — how often it answered when it should have declined.
* **echoed AND claimed** — input returned unchanged and reported as done. This
  is the failure that looks like a success, and it must be zero.

The threshold sweep prints, for every candidate confidence threshold, how many
correct answers it would refuse and how many wrong ones it would run. See
ADR 0012 for what the first runs showed.
