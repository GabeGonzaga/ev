"""Tier 0 and tier 1. Deterministic routing, no model, no network.

Tier 0 is what the user taught E.V.: an exact phrase mapped to an exact call.
Tier 1 is a small set of regular expressions. A hit here costs microseconds and
never reaches Ollama, which is the whole point -- `resolve()` returns `None`
when it has nothing, and the model router takes it from there in phase 1.

Two rules shape everything below:

* The utterance arrives verbatim. Nothing is translated before routing: the
  proper nouns in an utterance are precisely the tool arguments, and a
  mistranslated argument is a failure that looks like a success.
* Rules for every language are always live. A request is not tagged with a
  language before it gets here, and real input is mixed anyway
  ("abre o Visual Studio Code").

Captured groups keep the case the user typed. Matching is case-insensitive,
but "abre Blonde" must not become "blonde".
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.resolution import Resolution

STATIC_CONFIDENCE = 1.0
"""A static hit is not a guess. Tier 2 is where confidence starts to vary."""

_WHITESPACE = re.compile(r"\s+")
_TRAILING = ".!?,;:…"
_SCHEME = re.compile(r"^https?://", re.IGNORECASE)

_URL = r"(?P<url>https?://\S+|[\w-]+(?:\.[\w-]+)+(?:/\S*)?)"

_FILE_SUFFIXES = frozenset(
    {
        "app", "csv", "dmg", "doc", "docx", "gif", "jpeg", "jpg", "json", "key",
        "md", "mov", "mp3", "mp4", "numbers", "pages", "pdf", "png", "ppt",
        "pptx", "py", "txt", "xls", "xlsx", "zip",
    }
)  # fmt: skip


class LearnedPhrase(BaseModel):
    """One tier 0 entry: what the user said, and what it should do."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)


def prepare(utterance: str) -> str:
    """Collapse whitespace and drop trailing punctuation. Case is preserved."""
    text = unicodedata.normalize("NFC", utterance).strip()
    return _WHITESPACE.sub(" ", text).rstrip(_TRAILING)


def normalise(utterance: str) -> str:
    """The tier 0 lookup key. Casefolded, so accents survive and case does not."""
    return prepare(utterance).casefold()


def _url(groups: Mapping[str, str]) -> dict[str, object] | None:
    url = groups["url"]

    if _SCHEME.match(url):
        return {"url": url}

    # "open report.pdf" is not a website. Without a scheme, a filename-shaped
    # token is more likely a file than a domain, and guessing wrong sends the
    # user to a browser error page. Escalate instead of inventing a target.
    if url.split("/", 1)[0].rsplit(".", 1)[-1].casefold() in _FILE_SUFFIXES:
        return None

    # Spoken URLs have no scheme. https, never http -- the choice is the
    # router's, deterministic, and the safer of the two.
    return {"url": f"https://{url}"}


_KINDS = {
    "album": "album",
    "record": "album",
    "álbum": "album",
    "albúm": "album",
    "disco": "album",
    "track": "track",
    "song": "track",
    "faixa": "track",
    "música": "track",
    "musica": "track",
    "tema": "track",
    "playlist": "playlist",
    "lista": "playlist",
}
_KIND = "|".join(sorted(_KINDS, key=len, reverse=True))


def _play(groups: Mapping[str, str]) -> dict[str, object] | None:
    # The kind word is required by the pattern. "play Blonde" is ambiguous
    # between an album and a track, so it escalates rather than picking one.
    kind = _KINDS.get(groups["kind"].casefold())
    if kind is None:
        return None
    return {"name": groups["name"].strip(), "kind": kind}


_LANGUAGES = {
    "portuguese": "pt-PT",
    "português": "pt-PT",
    "portugues": "pt-PT",
    "english": "en",
    "inglês": "en",
    "ingles": "en",
    "spanish": "es",
    "espanhol": "es",
    "french": "fr",
    "francês": "fr",
    "frances": "fr",
    "german": "de",
    "alemão": "de",
    "alemao": "de",
    "italian": "it",
    "italiano": "it",
}
_LANGUAGE = "|".join(sorted(_LANGUAGES, key=len, reverse=True))


def _translate(groups: Mapping[str, str]) -> dict[str, object] | None:
    language = _LANGUAGES.get(groups["language"].casefold())
    if language is None:
        return None

    text = groups["text"].strip()
    if not text:
        return None

    return {"text": text, "to": language}


@dataclass(frozen=True, slots=True)
class Rule:
    tool: str
    pattern: re.Pattern[str]
    build: Callable[[Mapping[str, str]], dict[str, object] | None]


def _rule(
    tool: str,
    pattern: str,
    build: Callable[[Mapping[str, str]], dict[str, object] | None],
) -> Rule:
    return Rule(tool=tool, pattern=re.compile(pattern, re.IGNORECASE), build=build)


RULES: tuple[Rule, ...] = (
    _rule(
        "browser.open_url",
        rf"^(?:please\s+)?(?:open|go\s+to|browse\s+to|visit|pull\s+up)\s+"
        rf"(?:the\s+)?(?:site\s+|website\s+|page\s+)?{_URL}$",
        _url,
    ),
    _rule(
        "browser.open_url",
        rf"^(?:por\s+favor\s+)?(?:abre|abrir|abra|vai\s+ao|vai\s+à|vai\s+a|"
        rf"vai\s+para)\s+(?:o\s+|a\s+)?(?:site\s+|página\s+|pagina\s+)?{_URL}$",
        _url,
    ),
    _rule(
        "music.play",
        rf"^(?:please\s+)?(?:play|put\s+on)\s+(?:the\s+)?(?P<kind>{_KIND})\s+"
        rf"(?P<name>.+)$",
        _play,
    ),
    _rule(
        "music.play",
        rf"^(?:por\s+favor\s+)?(?:toca|tocar|põe|poe|coloca|pôe)\s+"
        rf"(?:o\s+|a\s+)?(?P<kind>{_KIND})\s+(?P<name>.+)$",
        _play,
    ),
    # Quoted only. Without quotation marks there is no way to tell where the
    # text to translate ends and the instruction resumes, and guessing would
    # send half a sentence to the model as if it were the whole of it.
    _rule(
        "language.translate",
        rf"^(?:please\s+)?translate\s+[\"'“](?P<text>.+)[\"'”]\s+"
        rf"(?:in)?to\s+(?P<language>{_LANGUAGE})$",
        _translate,
    ),
    _rule(
        "language.translate",
        rf"^(?:por\s+favor\s+)?(?:traduz|traduzir|traduza)\s+[\"'“](?P<text>.+)[\"'”]\s+"
        rf"(?:para|em)\s+(?:o\s+|a\s+)?(?P<language>{_LANGUAGE})$",
        _translate,
    ),
)


class StaticRouter:
    """Tier 0 then tier 1. `None` means "not mine", not "no".

    Phrases are injected rather than loaded from disk: routing is a pure
    decision, and reading `phrases.json` is the caller's job.
    """

    def __init__(
        self,
        *,
        rules: Sequence[Rule] = RULES,
        phrases: Mapping[str, LearnedPhrase] | None = None,
    ) -> None:
        self._rules = tuple(rules)
        self._phrases = {
            normalise(phrase): learned for phrase, learned in (phrases or {}).items()
        }

    def resolve(self, utterance: str) -> Resolution | None:
        prepared = prepare(utterance)

        learned = self._phrases.get(prepared.casefold())
        if learned is not None:
            return Resolution(
                tool=learned.tool,
                arguments=dict(learned.arguments),
                confidence=STATIC_CONFIDENCE,
            )

        for rule in self._rules:
            match = rule.pattern.match(prepared)
            if match is None:
                continue

            groups = {
                name: value
                for name, value in match.groupdict().items()
                if value is not None
            }
            arguments = rule.build(groups)
            if arguments is None:
                continue

            return Resolution(
                tool=rule.tool, arguments=arguments, confidence=STATIC_CONFIDENCE
            )

        return None
