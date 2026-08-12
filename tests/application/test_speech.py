from __future__ import annotations

from ev.application.speech import DEFAULT_LOCALE, PHRASES, Speaker


def test_it_answers_in_the_language_it_was_asked_in() -> None:
    # CLAUDE.md: detect the language of the request and answer in the same one.
    # Until this existed, a Portuguese voice read English words aloud.
    assert Speaker("pt-PT").say("music.playing", name="Blonde") == "A tocar Blonde"
    assert Speaker("en").say("music.playing", name="Blonde") == "Playing Blonde"


def test_an_unbound_speaker_speaks_english() -> None:
    # A CLI invocation with no locale is not a Portuguese one, and guessing
    # from the utterance would mean detecting the language before routing.
    assert Speaker().say("music.paused") == "Paused"
    assert Speaker(None).locale == DEFAULT_LOCALE


def test_binding_changes_the_language_of_the_next_turn() -> None:
    speaker = Speaker()
    speaker.bind("pt-PT")

    assert speaker.say("music.paused") == "Em pausa"

    speaker.bind(None)

    assert speaker.say("music.paused") == "Paused"


def test_an_unknown_locale_falls_back_rather_than_failing() -> None:
    assert Speaker("ja").say("music.paused") == "Paused"


def test_every_language_says_everything() -> None:
    # A half-translated phrasebook is how a sentence comes out in two
    # languages at once.
    english = set(PHRASES["en"])
    for locale, phrases in PHRASES.items():
        assert set(phrases) == english, f"{locale} is missing or has extra keys"


def test_the_portuguese_is_european() -> None:
    # pt-PT, not pt-BR: "a tocar" rather than "tocando", and the second person
    # the rest of the project uses.
    portuguese = PHRASES["pt-PT"]

    assert "A tocar" in portuguese["music.playing"]
    assert not any("tocando" in phrase for phrase in portuguese.values())
