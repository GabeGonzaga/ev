"""Shared fixtures.

`tests/fakes/bin/` is prepended to PATH, so adapters resolve the fake instead
of the real executable and the suite runs on Linux. Nothing mocks
`subprocess`: the assertion is on the argv that actually crossed the boundary.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

FAKE_BIN = Path(__file__).parent / "fakes" / "bin"


@dataclass
class FakeBin:
    log: Path

    def runs(self) -> list[list[str]]:
        """Every run, as [command, *arguments].

        The log is NUL-separated and each run is prefixed with its argument
        count, so a multi-line AppleScript source arrives here byte for byte.
        """
        if not self.log.exists():
            return []

        tokens = self.log.read_text(encoding="utf-8").split("\0")
        if tokens and tokens[-1] == "":
            tokens.pop()

        runs: list[list[str]] = []
        index = 0
        while index < len(tokens):
            count = int(tokens[index])
            runs.append(tokens[index + 1 : index + 2 + count])
            index += 2 + count
        return runs

    def command(self) -> str:
        """The executable of the last run, by the name the adapter asked for."""
        return self.runs()[-1][0]

    def argv(self) -> list[str]:
        """The arguments of the last run, without the executable."""
        return self.runs()[-1][1:]

    def was_run(self) -> bool:
        return bool(self.runs())


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeBin]:
    log = tmp_path / "argv.log"
    monkeypatch.setenv("PATH", f"{FAKE_BIN}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("EV_FAKE_LOG", str(log))
    yield FakeBin(log=log)
