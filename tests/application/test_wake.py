"""Whether that was E.V.'s name, in the languages it is spoken in."""

from __future__ import annotations

from pathlib import Path

import pytest

from ev.application.wake import WakeWord, flatten, hear, spellings
from ev.infrastructure.wake import load_wake, save_wake, wake_path


def listening(word: str = "ev", *also: str) -> WakeWord:
    return WakeWord(word=word, also=tuple(also), enabled=True)


# --- the name --------------------------------------------------------------


def test_a_bare_name_wakes_and_asks_for_nothing() -> None:
    # Nothing after it: the person is about to speak, so E.V. should listen
    # rather than guess what they meant.
    heard = hear("EV", listening())

    assert heard.woke
    assert heard.rest == ""


def test_a_name_and_a_request_arrive_together() -> None:
    heard = hear("EV, toca o álbum Blonde", listening())

    assert heard.woke
    assert heard.rest == "toca o álbum blonde"


def test_whisper_may_spell_two_letters_any_way_it_likes() -> None:
    """The hard case, and the one that was chosen.

    Two letters and a third of a second: `E.V.`, `E.V`, `EV`, `E V` are all
    the same thing said once.
    """
    for spelling in ("E.V.", "E.V", "EV", "E V", "ev."):
        assert hear(f"{spelling} play something", listening()).woke, spelling


def test_a_name_the_microphone_hears_differently_can_be_added() -> None:
    # No amount of cleverness predicts what a particular voice and a
    # particular microphone produce. What it does produce goes in the file.
    assert not hear("Evie, play something", listening()).woke
    assert hear("Evie, play something", listening("ev", "evie")).woke


def test_hey_and_ok_are_not_part_of_anyones_name() -> None:
    assert hear("hey EV, pause", listening()).rest == "pause"
    assert hear("ok EV", listening()).woke
    assert hear("olá EV, obrigado", listening()).woke


def test_another_user_can_call_it_something_else() -> None:
    # The whole reason the word is transcribed rather than pattern-matched:
    # a name nobody trained a model for still works.
    ana = listening("jarvis")

    assert hear("Jarvis, open github", ana).rest == "open github"
    assert not hear("EV, open github", ana).woke


def test_a_multi_word_name_works() -> None:
    heard = hear("hey computer, what time is it", listening("computer"))

    assert heard.woke
    assert heard.rest == "what time is it"


# --- what must not wake it -------------------------------------------------


def test_a_name_in_the_middle_of_a_sentence_is_somebody_talking_about_it() -> None:
    """The failure that makes people turn a wake word off for good.

    "I was telling Ana that E.V. can play music" is not an instruction, and
    acting on it is worse than missing a real one.
    """
    assert not hear("I was telling Ana that EV can play music", listening()).woke


def test_a_word_that_merely_starts_the_same_does_not_wake_it() -> None:
    assert not hear("every time I try this", listening()).woke
    assert not hear("evening", listening()).woke


def test_silence_and_room_noise_wake_nothing() -> None:
    assert not hear("", listening()).woke
    assert not hear("   ...  ", listening()).woke


# --- the shapes ------------------------------------------------------------


def test_accents_survive_and_punctuation_does_not() -> None:
    # `avó` is not `avo` in pt-PT, and a name is allowed to have an accent.
    assert flatten("Avó!") == "avó"
    assert flatten("E.V.") == "e v"


def test_the_letters_are_accepted_spaced_or_joined() -> None:
    assert spellings("ev") == {"ev", "e v"}


# --- the file --------------------------------------------------------------


def test_the_name_survives_a_restart(tmp_path: Path) -> None:
    path = wake_path(tmp_path)
    save_wake(path, WakeWord(word="jarvis", also=("javis",), enabled=True))

    read = load_wake(path)

    assert read.word == "jarvis"
    assert read.also == ("javis",)
    assert read.enabled


def test_listening_is_off_until_it_is_asked_for(tmp_path: Path) -> None:
    # Always-on listening is a decision somebody makes, not a default they
    # discover.
    assert not load_wake(wake_path(tmp_path)).enabled
    assert not WakeWord().enabled


def test_a_nameless_file_is_an_error_not_a_shrug(tmp_path: Path) -> None:
    path = wake_path(tmp_path)
    path.write_text('{"word": "  ", "enabled": true}', encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be empty"):
        load_wake(path)


# --- what this microphone actually produces -------------------------------


def test_the_default_spellings_are_the_measured_ones() -> None:
    """Not guessed: said into this machine, "E.V." comes back four ways.

    `EV` plainly, `Evie` when the sentence is Portuguese, `H-E-V` when "hey"
    runs into it, and `EV.` with a full stop when it is said alone.
    """
    default = WakeWord(enabled=True)

    for written in ("EV.", "H-E-V, pause", "Evie, toca o álbum Blonde", "EV play"):
        assert hear(written, default).woke, written


def test_a_name_that_is_also_a_word_is_not_a_default() -> None:
    # `heavy` is what "hey E.V." sometimes becomes, and it is also something
    # people say. A wake word that fires on "heavy rain tomorrow" is one
    # nobody keeps switched on.
    assert not hear("heavy rain tomorrow", WakeWord(enabled=True)).woke
    assert not hear("every evening", WakeWord(enabled=True)).woke
