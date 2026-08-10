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

    def argv(self) -> list[str]:
        """Every argument the fake executable was given, in order."""
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()

    def was_run(self) -> bool:
        return self.log.exists()


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeBin]:
    log = tmp_path / "argv.log"
    monkeypatch.setenv("PATH", f"{FAKE_BIN}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("EV_FAKE_LOG", str(log))
    yield FakeBin(log=log)
