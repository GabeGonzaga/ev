"""How much of an application E.V. is allowed to touch, and what it costs.

Two scales that meet at every call.

`AccessLevel` is the user's answer about one application: everything from "act
without asking" to "never". It is theirs to set and it is per application,
because trusting E.V. with Music says nothing about trusting it with Mail.

`Assurance` is what a particular call has to satisfy before it runs. It comes
from the stronger of two things -- the level the application was given, and the
risk the tool declares -- because an application you trust does not make
emptying the Trash reversible.

Nothing here reads a file or asks anyone anything. It is the vocabulary; the
policy in `ev/application/` does the deciding.
"""

from __future__ import annotations

from enum import StrEnum

from ev.domain.risk import RiskLevel


class AccessLevel(StrEnum):
    """What the user has said about one application."""

    OPEN = "open"
    """Act without asking. For the ones used constantly, by name, all day."""

    ASK = "ask"
    """Ask first, every time. The default for an application nobody has
    decided about, because acting unasked on something unknown is the one
    outcome nobody wants."""

    VERIFY = "verify"
    """Ask macOS to verify the owner first. Not a dialog E.V. draws -- the
    system's own, which E.V. cannot fake and cannot answer."""

    BLOCKED = "blocked"
    """Never. E.V. refuses and says so, and no phrasing gets around it."""


ORDER = {
    AccessLevel.OPEN: 0,
    AccessLevel.ASK: 1,
    AccessLevel.VERIFY: 2,
    AccessLevel.BLOCKED: 3,
}
"""Strength, so two answers can be compared. Nothing else may assume the
declaration order of the enum means anything."""


class Assurance(StrEnum):
    """What a call must satisfy before it runs."""

    NONE = "none"

    ACK = "ack"
    """A yes from whoever is at the machine: a click in the panel, a keypress
    in the terminal. It proves someone is there, not who."""

    OWNER = "owner"
    """macOS verifies the owner -- Touch ID or the login password, whichever
    they have. E.V. never sees the password and never asks for it: a program
    that draws its own password box is teaching people to type it into
    programs."""

    OWNER_AND_PASSWORD = "owner_and_password"
    """Both, for what cannot be undone or what speaks to other people in the
    user's name. The strongest thing this machine can be asked for."""


STRENGTH = {
    Assurance.NONE: 0,
    Assurance.ACK: 1,
    Assurance.OWNER: 2,
    Assurance.OWNER_AND_PASSWORD: 3,
}


FROM_LEVEL = {
    AccessLevel.OPEN: Assurance.NONE,
    AccessLevel.ASK: Assurance.ACK,
    AccessLevel.VERIFY: Assurance.OWNER,
    # BLOCKED never becomes an assurance: there is nothing to satisfy, and
    # offering one would turn a refusal into a challenge.
}

FROM_RISK = {
    RiskLevel.SAFE: Assurance.NONE,
    RiskLevel.SENSITIVE: Assurance.NONE,
    RiskLevel.DESTRUCTIVE: Assurance.OWNER,
}
"""Risk alone, before the application is considered.

SENSITIVE asks for nothing here on purpose: it is what playing an album and
writing a note are, and a password to play an album is a password nobody will
keep typing. What makes those ask is the *application's* level, which is the
user's to raise.
"""


def strongest(*assurances: Assurance) -> Assurance:
    """The one that satisfies all of them. Floors, never ceilings."""
    return max(assurances, key=lambda assurance: STRENGTH[assurance])
