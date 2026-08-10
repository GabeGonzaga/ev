from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.domain.results import ToolError, ToolErrorCode, ToolResult


def test_success_carries_no_error() -> None:
    result = ToolResult.success("browser.open_url", data={"url": "https://a.test"})

    assert result.ok
    assert result.error is None
    assert result.data == {"url": "https://a.test"}


def test_failure_carries_a_typed_code() -> None:
    result = ToolResult.failure(
        "music.play", ToolErrorCode.ADAPTER_FAILED, "Music is not running"
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED


def test_ok_and_error_cannot_disagree() -> None:
    with pytest.raises(ValidationError):
        ToolResult(ok=False, tool="music.play")

    with pytest.raises(ValidationError):
        ToolResult(
            ok=True,
            tool="music.play",
            error=ToolError(code=ToolErrorCode.TIMEOUT, message="too slow"),
        )


def test_results_are_frozen() -> None:
    result = ToolResult.success("system.sleep")

    with pytest.raises(ValidationError):
        result.ok = False


def test_error_codes_are_stable_wire_values() -> None:
    # These strings land in the journal and cross the IPC boundary in phase 1.5.
    # Renaming one is a migration, not a rename.
    assert [code.value for code in ToolErrorCode] == [
        "unknown_tool",
        "invalid_arguments",
        "permission_denied",
        "confirmation_declined",
        "adapter_failed",
        "timeout",
    ]
