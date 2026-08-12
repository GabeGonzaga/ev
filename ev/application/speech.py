"""What E.V. says, in the language it was asked in.

`CLAUDE.md`: detect the language of the request and answer in the same one.
Until now every tool composed its line in English, which was invisible while
everything was printed and obvious the moment Joana read "Opening example.com"
aloud.

No model is involved. These lines are written by us, not generated, so they are
written once per language and looked up -- "do not add an LLM call that an
existing call could have covered", and this one needs no call at all.

The locale changes per turn and the services are built once, so `Speaker` is
bound per turn under the same lock that serialises everything else, exactly as
the confirmation port is.
"""

from __future__ import annotations

DEFAULT_LOCALE = "en"

PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "browser.opening": "Opening {host}",
        "music.playing": "Playing {name}",
        "music.playing_from": "Playing {name}, from {track}",
        "music.playing_instead": "No album called {asked}. Playing the playlist {name}",
        "music.paused": "Paused",
        "music.resumed": "Playing",
        "music.next": "Skipped",
        "music.previous": "Went back",
        "music.stopped": "Stopped",
        "music.volume": "Volume {level}",
        "music.muted": "Muted",
        "music.unmuted": "Sound back on",
        "music.no_playlist": "No playlist matches {name}. You have: {existing}",
        "unsure": "Did you mean {guess}? I am only {confidence} sure.",
        "not_understood": "I did not understand that.",
    },
    "pt-PT": {
        # European Portuguese. "Ecrã" not "tela", "a tocar" not "tocando".
        "browser.opening": "A abrir {host}",
        "music.playing": "A tocar {name}",
        "music.playing_from": "A tocar {name}, a partir de {track}",
        "music.playing_instead": (
            "Não há nenhum álbum chamado {asked}. A tocar a playlist {name}"
        ),
        "music.paused": "Em pausa",
        "music.resumed": "A tocar",
        "music.next": "Saltei",
        "music.previous": "Voltei atrás",
        "music.stopped": "Parei",
        "music.volume": "Volume {level}",
        "music.muted": "Sem som",
        "music.unmuted": "Som de volta",
        "music.no_playlist": "Nenhuma playlist corresponde a {name}. Tens: {existing}",
        "unsure": "Querias dizer {guess}? Só tenho {confidence} de certeza.",
        "not_understood": "Não percebi.",
    },
}


class Speaker:
    """The voice of one turn.

    Unbound, it speaks English -- a CLI invocation with no locale is not a
    Portuguese one, and guessing from the utterance would mean detecting the
    language before routing, which `CLAUDE.md` forbids for good reasons.
    """

    def __init__(self, locale: str | None = None) -> None:
        self._locale = locale or DEFAULT_LOCALE

    def bind(self, locale: str | None) -> None:
        self._locale = locale or DEFAULT_LOCALE

    @property
    def locale(self) -> str:
        return self._locale

    def say(self, key: str, **values: object) -> str:
        """The line for this key, in this locale.

        A missing translation falls back to English rather than to the key: a
        user hearing the wrong language is a defect, and a user hearing
        "music.playing" is a bug report.
        """
        phrases = PHRASES.get(self._locale) or PHRASES[DEFAULT_LOCALE]
        template = phrases.get(key) or PHRASES[DEFAULT_LOCALE][key]
        return template.format(**values)
