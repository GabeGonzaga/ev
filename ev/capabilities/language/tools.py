"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.language.args import TranslateArgs
from ev.capabilities.language.service import TRANSLATE, LanguageService
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


def language_tools(service: LanguageService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=TRANSLATE,
            description=(
                "Translate text into another language. Returns the translation; "
                "changes nothing on the machine."
            ),
            args=TranslateArgs,
            risk=RiskLevel.SAFE,
            handler=service.translate,
            # It writes text and touches nothing. No TCC surface is involved.
            permissions=frozenset(),
        ),
    )
