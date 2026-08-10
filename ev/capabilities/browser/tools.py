"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.browser.args import OpenUrlArgs
from ev.capabilities.browser.service import OPEN_URL, BrowserService
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


def browser_tools(service: BrowserService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=OPEN_URL,
            description="Open an http or https URL in the default browser.",
            args=OpenUrlArgs,
            risk=RiskLevel.SAFE,
            handler=service.open_url,
            # open(1) needs no TCC permission. Nothing is declared that is not
            # actually required: the policy denies on anything ungranted, so an
            # over-declared permission would make the tool unreachable.
            permissions=frozenset(),
        ),
    )
