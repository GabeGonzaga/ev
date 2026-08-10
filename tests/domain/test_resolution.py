from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.domain.resolution import Resolution


def test_confidence_is_bounded() -> None:
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            Resolution(tool="music.play", confidence=bad)


def test_arguments_default_to_empty() -> None:
    resolution = Resolution(tool="system.sleep", confidence=1.0)

    assert resolution.arguments == {}
    assert resolution.response is None


def test_resolutions_are_frozen() -> None:
    # A proposal must not be edited between routing and validation.
    resolution = Resolution(tool="music.play", confidence=0.9)

    with pytest.raises(ValidationError):
        resolution.tool = "system.shutdown"
