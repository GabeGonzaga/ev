"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.vision.args import LookArgs
from ev.capabilities.vision.service import LOOK, VisionService
from ev.domain.permissions import Permission
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


def vision_tools(service: VisionService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=LOOK,
            description=(
                "Answer a question about what the camera is showing right now. "
                "Only works when the user has just taken a frame."
            ),
            args=LookArgs,
            # Nothing on the machine changes, so it is not DESTRUCTIVE. It is
            # not SAFE either: it looks at a camera frame, and the permission
            # gate below is the point of saying so.
            risk=RiskLevel.SENSITIVE,
            handler=service.look,
            permissions=frozenset({Permission.CAMERA}),
        ),
    )
