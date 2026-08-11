from __future__ import annotations

from pathlib import Path

import pytest

from ev.infrastructure.macos.processes import ProcessRunner
from ev.infrastructure.speech.recognizer import (
    Transcription,
    WhisperCppRecognizer,
    clean,
    language_code,
)
from tests.conftest import FakeBin


@pytest.fixture
def model(tmp_path: Path) -> Path:
    path = tmp_path / "ggml-small.bin"
    path.write_bytes(b"not really a model")
    return path


# --- the language is always stated ----------------------------------------


@pytest.mark.asyncio
async def test_the_language_reaches_whisper_and_is_never_auto(
    fake_bin: FakeBin, model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Auto-detect is unreliable on the short utterances that are the normal
    # case, and a misdetected language becomes a tool argument.
    monkeypatch.setenv("EV_FAKE_STDOUT", "abre o Visual Studio Code")
    recognizer = WhisperCppRecognizer(ProcessRunner(), model=model)

    await recognizer.transcribe(Path("/tmp/utterance.wav"), language="pt-PT")

    assert fake_bin.command() == "whisper-cli"
    assert fake_bin.argv() == [
        "--model",
        str(model),
        "--language",
        "pt",
        "--threads",
        "4",
        "--no-timestamps",
        "--no-prints",
        "--file",
        "/tmp/utterance.wav",
    ]
    assert "auto" not in fake_bin.argv()


def test_a_locale_becomes_a_whisper_language() -> None:
    assert language_code("pt-PT") == "pt"
    assert language_code("en") == "en"


def test_an_unknown_language_is_refused_with_the_known_ones() -> None:
    with pytest.raises(Transcription, match="pt-PT"):
        language_code("klingon")


# --- what comes back ------------------------------------------------------


@pytest.mark.asyncio
async def test_the_transcript_is_returned(
    fake_bin: FakeBin, model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "  toca o álbum Blonde \n")
    recognizer = WhisperCppRecognizer(ProcessRunner(), model=model)

    said = await recognizer.transcribe(Path("/tmp/a.wav"), language="pt-PT")

    assert said == "toca o álbum Blonde"


@pytest.mark.asyncio
async def test_whispers_annotations_are_not_words_the_user_said(
    fake_bin: FakeBin, model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # [BLANK_AUDIO] and (wind blowing) describe the recording. Routed as text
    # they would become an utterance nobody spoke.
    monkeypatch.setenv("EV_FAKE_STDOUT", "[MUSIC] abre example.com (wind blowing)")
    recognizer = WhisperCppRecognizer(ProcessRunner(), model=model)

    said = await recognizer.transcribe(Path("/tmp/a.wav"), language="en")

    assert said == "abre example.com"


def test_annotation_only_output_is_nothing() -> None:
    assert clean("[BLANK_AUDIO]") == ""


@pytest.mark.asyncio
async def test_silence_is_refused_rather_than_invented(
    fake_bin: FakeBin, model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "[BLANK_AUDIO]\n")
    recognizer = WhisperCppRecognizer(ProcessRunner(), model=model)

    with pytest.raises(Transcription, match="nothing was said"):
        await recognizer.transcribe(Path("/tmp/quiet.wav"), language="pt-PT")


@pytest.mark.asyncio
async def test_a_failing_whisper_is_a_transcription_error(
    fake_bin: FakeBin, model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv("EV_FAKE_STDERR", "failed to read wav")
    recognizer = WhisperCppRecognizer(ProcessRunner(), model=model)

    with pytest.raises(Transcription, match="failed to read wav"):
        await recognizer.transcribe(Path("/tmp/a.wav"), language="pt-PT")


@pytest.mark.asyncio
async def test_a_missing_model_says_how_to_get_it(
    fake_bin: FakeBin, tmp_path: Path
) -> None:
    recognizer = WhisperCppRecognizer(ProcessRunner(), model=tmp_path / "absent.bin")

    with pytest.raises(Transcription, match="make models"):
        await recognizer.transcribe(Path("/tmp/a.wav"), language="pt-PT")

    # Nothing was run: there was nothing to run it with.
    assert not fake_bin.was_run()
