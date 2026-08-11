from __future__ import annotations

import pytest

from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner
from tests.conftest import FakeBin

pytestmark = pytest.mark.asyncio

SCRIPT = "on run argv\n\treturn item 1 of argv\nend run"


async def test_the_script_is_one_argument_and_values_follow_it(
    fake_bin: FakeBin,
) -> None:
    await AppleScriptClient(ProcessRunner()).run(SCRIPT, "Blonde", "album")

    assert fake_bin.command() == "osascript"
    assert fake_bin.argv() == ["-e", SCRIPT, "--", "Blonde", "album"]


async def test_stdout_comes_back_stripped(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "Nikes\n")

    assert await AppleScriptClient(ProcessRunner()).run(SCRIPT) == "Nikes"


async def test_an_execution_error_loses_its_prefix_and_code(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    # What is left is a sentence that can be spoken.
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv("EV_FAKE_STDERR", "execution error: Music got an error (-1728)")

    with pytest.raises(AppleScriptError, match=r"^Music got an error$"):
        await AppleScriptClient(ProcessRunner()).run(SCRIPT)


async def test_a_refused_apple_event_keeps_the_systems_wording(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This is the TCC denial. E.V. asserting a permission it does not have
    # ends here, with macOS having the last word.
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv(
        "EV_FAKE_STDERR",
        "execution error: Not authorized to send Apple events to Music. (-1743)",
    )

    with pytest.raises(AppleScriptError, match="Not authorized to send Apple events"):
        await AppleScriptClient(ProcessRunner()).run(SCRIPT)


async def test_a_silent_failure_still_says_something(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "1")

    with pytest.raises(AppleScriptError, match="osascript failed"):
        await AppleScriptClient(ProcessRunner()).run(SCRIPT)
