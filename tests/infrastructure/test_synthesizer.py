from __future__ import annotations

import pytest

from ev.infrastructure.macos.processes import ProcessRunner
from ev.infrastructure.speech.synthesizer import SaySynthesizer
from tests.conftest import FakeBin

pytestmark = pytest.mark.asyncio


async def test_the_exact_argv_reaches_say(fake_bin: FakeBin) -> None:
    await SaySynthesizer(ProcessRunner()).speak("Opening github.com")

    assert fake_bin.command() == "say"
    assert fake_bin.argv() == ["--", "Opening github.com"]


async def test_portuguese_is_spoken_by_a_european_voice(fake_bin: FakeBin) -> None:
    # Without naming Joana, macOS reads a Portuguese sentence with the system
    # default, which is usually Brazilian or English. The locale is not enough
    # on its own -- the voice has to be asked for.
    await SaySynthesizer(ProcessRunner()).speak("A tocar Blonde", voice="pt-PT")

    assert fake_bin.argv() == ["-v", "Joana", "--", "A tocar Blonde"]


async def test_an_unknown_locale_uses_the_system_voice(fake_bin: FakeBin) -> None:
    await SaySynthesizer(ProcessRunner()).speak("Playing Blonde", voice="ja")

    assert fake_bin.argv() == ["--", "Playing Blonde"]


async def test_a_sentence_starting_with_a_dash_is_still_a_sentence(
    fake_bin: FakeBin,
) -> None:
    # The text is the user's or the model's, so it is never trusted to be
    # anything but text.
    await SaySynthesizer(ProcessRunner()).speak("-v evil")

    assert fake_bin.argv() == ["--", "-v evil"]


async def test_failing_to_speak_does_not_raise(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The turn already happened and the words are on screen. Losing the audio
    # is not a reason to report a failure that did not occur.
    monkeypatch.setenv("EV_FAKE_EXIT", "1")

    await SaySynthesizer(ProcessRunner()).speak("Opening github.com")
