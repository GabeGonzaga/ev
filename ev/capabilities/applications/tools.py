"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.applications.args import ApplicationArgs
from ev.capabilities.applications.service import (
    OPEN,
    QUIT,
    ApplicationService,
    installed_name,
)
from ev.domain.permissions import Permission
from ev.domain.risk import RiskLevel
from ev.infrastructure.macos.applications import Applications
from ev.registry import ToolSpec


def application_tools(
    service: ApplicationService, applications: Applications
) -> tuple[ToolSpec[Any], ...]:
    def targeted(args: ApplicationArgs) -> str | None:
        """Which application the policy should be asked about.

        The resolved name when it resolves, and the spoken one when it does
        not: a level set on `Mail` must apply to a request for "mail", and an
        application nobody can find is still not something to wave through.
        """
        return installed_name(applications, args.name) or args.name

    return (
        ToolSpec(
            name=OPEN,
            description=(
                "Launch an application installed on this Mac, by name: "
                "'open Safari', 'abre o Spotify'. Only for applications. If "
                "the words name a website -- github, youtube, gmail -- use "
                "browser.open_url instead, even when no domain is spelled out."
            ),
            args=ApplicationArgs,
            # Launching is not destructive and it is undone by quitting. What
            # decides whether it happens is the application's own level.
            risk=RiskLevel.SENSITIVE,
            handler=service.open,
            # `open(1)` needs no TCC permission; nothing is declared that is
            # not actually required.
            permissions=frozenset(),
            application=targeted,
        ),
        ToolSpec(
            name=QUIT,
            description=(
                "Quit or close a running application, by name: 'quit Spotify', "
                "'fecha o Spotify', 'close Safari'. It is asked to quit, so it "
                "saves and closes its own documents."
            ),
            args=ApplicationArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.quit,
            # Quitting is an Apple Event, unlike opening.
            permissions=frozenset({Permission.APPLE_EVENTS}),
            application=targeted,
        ),
    )
