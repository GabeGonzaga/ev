"""What the permission policy is allowed to answer.

The policy itself lands in step 4. This is the vocabulary `Registry.call()`
already needs to route a call, kept here so the implementation arrives in its
documented home rather than leaking into the registry.
"""

from __future__ import annotations

from enum import StrEnum


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"
    """Ask the user first. A DESTRUCTIVE tool is confirmed whatever the policy
    answers -- see `Registry.call()`."""
