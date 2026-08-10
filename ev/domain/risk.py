"""How much damage a tool can do.

Three levels, because the policy only has three answers: run it, run it if
the permission is held, ask the user first.
"""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    """Declared per tool in `tools.py`, never inferred from the arguments."""

    SAFE = "safe"
    """No side effect the user would mind: reads, queries, opening a URL."""

    SENSITIVE = "sensitive"
    """Touches a guarded capability or changes state the user can undo."""

    DESTRUCTIVE = "destructive"
    """Loses data or is hard to reverse. Always confirmed, journalled urgently."""
