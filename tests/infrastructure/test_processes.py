from __future__ import annotations

import pytest

from ev.infrastructure.macos.processes import (
    ProcessFailed,
    ProcessNotFound,
    ProcessRunner,
)
from tests.conftest import FakeBin

pytestmark = pytest.mark.asyncio


async def test_argv_reaches_the_process_verbatim(fake_bin: FakeBin) -> None:
    completed = await ProcessRunner().run(["open", "--", "https://a.test"])

    assert fake_bin.argv() == ["--", "https://a.test"]
    assert completed.argv == ("open", "--", "https://a.test")
    assert completed.returncode == 0


async def test_arguments_are_never_word_split(fake_bin: FakeBin) -> None:
    # There is no shell, so this is one argument, not three and a redirect.
    await ProcessRunner().run(["open", "a b > c"])

    assert fake_bin.argv() == ["a b > c"]


async def test_a_nonzero_exit_raises_with_the_stderr(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "3")
    monkeypatch.setenv("EV_FAKE_STDERR", "no such thing")

    with pytest.raises(ProcessFailed, match="open exited 3: no such thing"):
        await ProcessRunner().run(["open", "x"])


async def test_check_false_returns_the_failure(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "3")

    completed = await ProcessRunner().run(["open", "x"], check=False)

    assert completed.returncode == 3


async def test_a_missing_executable_is_named(fake_bin: FakeBin) -> None:
    with pytest.raises(ProcessNotFound, match="ev_no_such_binary"):
        await ProcessRunner().run(["ev_no_such_binary"])


async def test_an_empty_argv_is_refused() -> None:
    with pytest.raises(ValueError, match="argv must not be empty"):
        await ProcessRunner().run([])


async def test_a_timeout_kills_the_process() -> None:
    runner = ProcessRunner()

    with pytest.raises(TimeoutError):
        await runner.run(["sleep", "5"], timeout=0.1)
