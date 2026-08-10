"""The TCC-facing capabilities and what the system currently says about them.

Types only. Permission state is reported by the signed native host through
typed events and is never inferred by the Python core (CLAUDE.md, invariant 7),
so nothing here probes anything.
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    """A capability macOS gates behind TCC."""

    MICROPHONE = "microphone"
    CAMERA = "camera"
    ACCESSIBILITY = "accessibility"
    APPLE_EVENTS = "apple_events"


class PermissionState(StrEnum):
    """What the host last reported for a permission."""

    GRANTED = "granted"
    DENIED = "denied"
    UNDETERMINED = "undetermined"
    """Never asked for. Distinct from DENIED: this one is worth prompting for."""
