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
        "music.playing_instead": "Nothing called {asked}. Playing {kind} {name}",
        "kind.album": "the album",
        "kind.artist": "the artist",
        "kind.track": "the track",
        "kind.playlist": "the playlist",
        "music.nothing_matches": (
            "Nothing in the library matches {name}. Your playlists: {existing}"
        ),
        "music.paused": "Paused",
        "music.resumed": "Playing",
        "music.resumed_track": "Playing {track}",
        "music.next": "Skipped",
        "music.next_track": "Skipped to {track}",
        "music.previous": "Went back",
        "music.previous_track": "Went back to {track}",
        "music.stopped": "Stopped",
        "music.seeked": "At {when}",
        "music.nothing_playing": "Nothing is playing.",
        "music.shuffle_on": "Shuffle on",
        "music.shuffle_off": "Shuffle off",
        "music.repeat_all": "Repeat on",
        "music.repeat_one": "Repeating this track",
        "music.repeat_off": "Repeat off",
        "music.switch_failed": "Music would not change {setting}.",
        "music.volume": "Volume {level}",
        "music.muted": "Muted",
        "music.unmuted": "Sound back on",
        "music.no_playlist": "No playlist matches {name}. You have: {existing}",
        "notes.created": "Saved {title} to Notes",
        "notes.created_in": "Saved {title} to {folder}",
        "notes.no_folder": "No folder called {name}. You have: {existing}",
        "reminders.created": "Reminder set: {title}",
        "reminders.created_at": "Reminder set: {title}, {when}",
        "reminders.no_list": "No list called {name}. You have: {existing}",
        "reminders.past": "{when} is in the past. Say when you meant.",
        "applications.opened": "Opening {name}",
        "applications.quit": "Closing {name}",
        "applications.unknown": "There is no application called {name} on this Mac.",
        "vision.nothing_to_see": "The camera is not on. Take a look first.",
        "vision.nothing": "I could not make anything of that.",
        "unsure": "Did you mean {guess}? I am only {confidence} sure.",
        "not_understood": "I did not understand that.",
        "macro.ran": "Ran {name}: {steps} steps",
        "macro.stopped": "{name} stopped at step {step} ({tool}): {why}",
        "macro.unknown": "No macro called {name}. You have: {existing}",
    },
    "pt-PT": {
        # European Portuguese. "Ecrã" not "tela", "a tocar" not "tocando".
        "browser.opening": "A abrir {host}",
        "music.playing": "A tocar {name}",
        "music.playing_from": "A tocar {name}, a partir de {track}",
        "music.playing_instead": "Não há nada chamado {asked}. A tocar {kind} {name}",
        "kind.album": "o álbum",
        "kind.artist": "o artista",
        "kind.track": "a faixa",
        "kind.playlist": "a playlist",
        "music.nothing_matches": (
            "Não há nada na biblioteca que corresponda a {name}. "
            "As tuas playlists: {existing}"
        ),
        "music.paused": "Em pausa",
        "music.resumed": "A tocar",
        "music.resumed_track": "A tocar {track}",
        "music.next": "Saltei",
        "music.next_track": "Saltei para {track}",
        "music.previous": "Voltei atrás",
        "music.previous_track": "Voltei para {track}",
        "music.stopped": "Parei",
        # "Aleatório" is what the Music app itself calls it in pt-PT; nobody
        # says "baralhado".
        "music.seeked": "Em {when}",
        "music.nothing_playing": "Não está nada a tocar.",
        "music.shuffle_on": "Aleatório ligado",
        "music.shuffle_off": "Aleatório desligado",
        "music.repeat_all": "Repetição ligada",
        "music.repeat_one": "A repetir esta faixa",
        "music.repeat_off": "Repetição desligada",
        "music.switch_failed": "A Música não mudou {setting}.",
        "music.volume": "Volume {level}",
        "music.muted": "Sem som",
        "music.unmuted": "Som de volta",
        "music.no_playlist": "Nenhuma playlist corresponde a {name}. Tens: {existing}",
        "notes.created": "Guardei {title} nas Notas",
        "notes.created_in": "Guardei {title} em {folder}",
        "notes.no_folder": "Não há nenhuma pasta chamada {name}. Tens: {existing}",
        "reminders.created": "Lembrete criado: {title}",
        "reminders.created_at": "Lembrete criado: {title}, {when}",
        "reminders.no_list": "Não há nenhuma lista chamada {name}. Tens: {existing}",
        "reminders.past": "{when} já passou. Diz-me quando querias.",
        "applications.opened": "A abrir {name}",
        "applications.quit": "A fechar {name}",
        "applications.unknown": "Não há nenhuma aplicação chamada {name} neste Mac.",
        "vision.nothing_to_see": "A câmara não está ligada. Mostra-me primeiro.",
        "vision.nothing": "Não consegui perceber o que era.",
        "unsure": "Querias dizer {guess}? Só tenho {confidence} de certeza.",
        "not_understood": "Não percebi.",
        "macro.ran": "Corri {name}: {steps} passos",
        "macro.stopped": "{name} parou no passo {step} ({tool}): {why}",
        "macro.unknown": "Não há nenhuma macro chamada {name}. Tens: {existing}",
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
