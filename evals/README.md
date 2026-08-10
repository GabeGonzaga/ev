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

Cases in this directory are deterministic and run in `make test`. Model
routing evals — tier 2, non-deterministic, needing weights — are `make eval`
and are not in CI.
