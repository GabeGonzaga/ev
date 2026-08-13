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

# Spoken URLs arrive damaged in predictable ways: whisper writes "github dot
# com", "github ponto com", or "github . com" for something a keyboard would
# have typed as one token. The pattern accepts those shapes and `_url` puts
# them back together; anything less predictable escalates rather than being
# guessed at.
_DOT = r"(?:\s*\.\s*|\s+(?:dot|ponto)\s+)"
_URL = rf"(?P<url>https?://\S+|[\w-]+(?:{_DOT}[\w-]+)+(?:/\S*)?)"
_SPOKEN_DOT = re.compile(_DOT, re.IGNORECASE)

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
    # "github dot com" and "github . com" are the same address as
    # "github.com". A URL has no spaces in it, so what is left after joining
    # the dots cannot keep any either.
    url = "".join(_SPOKEN_DOT.sub(".", groups["url"]).split())

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
    "artist": "artist",
    "artista": "artist",
    "banda": "artist",
    "grupo": "artist",
    "band": "artist",
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


_ACTIONS = {
    # English
    "pause": "pause",
    "resume": "resume",
    "continue": "resume",
    # Every music app's play button means resume. `music.play` needs a name,
    # so a bare "play" cannot be asking for one.
    "play": "resume",
    "keep going": "resume",
    "next": "next",
    "skip": "next",
    "previous": "previous",
    "go back": "previous",
    "back": "previous",
    "stop": "stop",
    # Portuguese
    "pausa": "pause",
    "pára": "stop",
    "para": "stop",
    "continua": "resume",
    "retoma": "resume",
    "próxima": "next",
    "proxima": "next",
    "seguinte": "next",
    "salta": "next",
    "anterior": "previous",
    "volta atrás": "previous",
    "volta atras": "previous",
}
_ACTION = "|".join(sorted(_ACTIONS, key=len, reverse=True))


def _control(groups: Mapping[str, str]) -> dict[str, object] | None:
    action = _ACTIONS.get(groups["action"].casefold())
    return None if action is None else {"action": action}


_CHANGES = {
    # English
    "up": "up",
    "louder": "up",
    "turn it up": "up",
    "volume up": "up",
    "down": "down",
    "quieter": "down",
    "turn it down": "down",
    "volume down": "down",
    "lower": "down",
    "mute": "mute",
    "silence": "mute",
    "unmute": "unmute",
    # Portuguese
    "mais alto": "up",
    "aumenta": "up",
    "aumenta o volume": "up",
    "mais baixo": "down",
    "baixa": "down",
    "baixa o volume": "down",
    "silencia": "mute",
    "sem som": "mute",
    "com som": "unmute",
}
_CHANGE = "|".join(sorted(_CHANGES, key=len, reverse=True))


def _step(groups: Mapping[str, str]) -> dict[str, object] | None:
    change = _CHANGES.get(groups["change"].casefold())
    return None if change is None else {"change": change}


def _volume(groups: Mapping[str, str]) -> dict[str, object] | None:
    level = int(groups["level"])
    # The args model bounds this too. Refusing here means a misheard "volume
    # 900" escalates instead of dying as INVALID_ARGUMENTS for something tier
    # 1 could see was not a volume.
    return {"level": level} if 0 <= level <= 100 else None


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


_WHEN = re.compile(
    r"\b(at\s+\d+|at\s+noon|tonight|tomorrow|today|this\s+(morning|afternoon|"
    r"evening)|next\s+\w+|on\s+(monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday)|in\s+\d+\s+(minutes?|hours?|days?)|in\s+an?\s+"
    r"(minute|hour|day)|amanh[ãa]|hoje|logo|daqui\s+a|[àa]s\s+\d+|ao\s+"
    r"(almo[çc]o|jantar)|na\s+(segunda|ter[çc]a|quarta|quinta|sexta)|"
    r"em\s+\d+\s+(minutos?|horas?|dias?)|no\s+dia\s+\d+|on\s+the\s+\d+|"
    r"na\s+lista|in\s+the\s+\S+\s+list)",
    re.IGNORECASE,
)
"""When a reminder stops being just a title.

Only the leading boundary is anchored. A closing one looks tidier and is wrong
here: a digit followed by a word boundary does not match "on the 15th" or
"às 15", because the character after the digits is a letter. This is a guard,
and one that sometimes matches half a word still escalates the right
utterance.

A date is not a name someone said: it is computed from the utterance and from
what day it is, which is the model's job and not a regular expression's. Tier 1
takes "remind me to call the dentist" and stands aside for the rest.
"""


def _remind(groups: Mapping[str, str]) -> dict[str, object] | None:
    title = groups["title"].strip()
    return None if _WHEN.search(title) else {"title": title}


_BODY = re.compile(
    r"\b(saying|that\s+says|which\s+says|with\s+the\s+text|about|"
    r"in\s+the\s+\S+\s+folder|a\s+dizer|que\s+diz|com\s+o\s+texto|"
    r"sobre|na\s+pasta|dentro\s+da\s+pasta)\b",
    re.IGNORECASE,
)
"""Where a title stops being a title. Tier 1 has no way to tell what belongs
to the note's name and what belongs in it, so it declines instead of guessing
-- the model does that part."""


def _note(groups: Mapping[str, str]) -> dict[str, object] | None:
    title = groups["title"].strip()
    return None if _BODY.search(title) else {"title": title}


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
    # Transport controls. Whatever is playing is already playing, so there is
    # nothing to capture but the verb.
    _rule(
        "music.control",
        rf"^(?:please\s+|por\s+favor\s+)?(?P<action>{_ACTION})"
        rf"(?:\s+(?:the\s+|this\s+|that\s+|a\s+|o\s+|esta\s+|esa\s+)?"
        rf"(?:music|song|track|música|musica|canção|cancao))?$",
        _control,
    ),
    _rule(
        "music.volume",
        r"^(?:set\s+)?(?:the\s+)?volume\s+(?:to\s+)?(?P<level>\d{1,3})$",
        _volume,
    ),
    # Relative, because nobody says "set the volume to 60" out loud.
    _rule(
        "music.volume",
        rf"^(?:please\s+|por\s+favor\s+)?(?:turn\s+(?:it|the\s+volume)\s+)?"
        rf"(?P<change>{_CHANGE})(?:\s+(?:o\s+)?volume)?$",
        _step,
    ),
    _rule(
        "music.volume",
        r"^(?:põe\s+|poe\s+|coloca\s+)?(?:o\s+)?volume\s+"
        r"(?:a\s+|em\s+|no\s+|nos\s+)?(?P<level>\d{1,3})$",
        _volume,
    ),
    # A macro is a name the user chose, so it is captured verbatim and matched
    # against the saved ones later -- the same rule as playlists.
    _rule(
        "macro.run",
        r"^(?:please\s+)?(?:run|start)\s+(?:the\s+)?macro\s+(?P<name>.+)$",
        lambda groups: {"name": groups["name"].strip()},
    ),
    _rule(
        "macro.run",
        r"^(?:por\s+favor\s+)?(?:corre|executa|faz)\s+(?:a\s+)?macro\s+"
        r"(?P<name>.+)$",
        lambda groups: {"name": groups["name"].strip()},
    ),
    # A title and nothing else. "Take a note called Boiler saying it was
    # serviced in March" carries a body, and a greedy capture titles the note
    # with the whole sentence -- a wrong argument that looks like a success.
    # Those escalate; a bare title lands here for free.
    _rule(
        "notes.create",
        r"^(?:please\s+)?(?:make|take|create|write|start)\s+(?:a\s+)?(?:new\s+)?"
        r"note\s+(?:called|titled|named)\s+(?P<title>.+)$",
        _note,
    ),
    _rule(
        "notes.create",
        r"^(?:por\s+favor\s+)?(?:cria|criar|faz|escreve|abre)\s+(?:uma\s+)?"
        r"(?:nova\s+)?nota\s+(?:chamada|com\s+o\s+nome|com\s+o\s+título|"
        r"com\s+o\s+titulo)\s+(?P<title>.+)$",
        _note,
    ),
    # Quitting, in both languages. "Open X" is deliberately absent: without a
    # domain it is a coin toss between an application and a website, and that
    # is a judgement, which is tier 2's job. Closing is not ambiguous.
    _rule(
        "applications.quit",
        r"^(?:please\s+)?(?:quit|close)\s+(?:the\s+)?(?:app\s+|application\s+)?"
        r"(?P<name>[\w .+-]{2,60})$",
        lambda groups: {"name": groups["name"].strip()},
    ),
    _rule(
        "applications.quit",
        r"^(?:por\s+favor\s+)?(?:fecha|fechar|sai\s+d[oa]|encerra)\s+"
        r"(?:o\s+|a\s+)?(?:app\s+|aplica[çc][ãa]o\s+)?"
        r"(?P<name>[\w .+-]{2,60})$",
        lambda groups: {"name": groups["name"].strip()},
    ),
    # A reminder with no date. Anything with a time in it escalates: see
    # `_WHEN`.
    _rule(
        "reminders.create",
        r"^(?:please\s+)?remind\s+me\s+(?:to\s+|about\s+|that\s+)?"
        r"(?P<title>.+)$",
        _remind,
    ),
    _rule(
        "reminders.create",
        r"^(?:por\s+favor\s+)?(?:lembra|lembre|relembra)[\s-]*me\s+"
        r"(?:de\s+|para\s+|que\s+)?(?P<title>.+)$",
        _remind,
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
