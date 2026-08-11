from __future__ import annotations

import pytest

from ev.application.policy import ConfidenceDecision, ConfidencePolicy
from ev.domain.resolution import Resolution


def proposal(confidence: float) -> Resolution:
    return Resolution(tool="music.play", arguments={}, confidence=confidence)


def test_a_static_hit_always_passes() -> None:
    # Tier 0 and tier 1 answer at 1.0. This policy exists for tier 2.
    assert ConfidencePolicy().decide(proposal(1.0)) is ConfidenceDecision.ACCEPT


def test_the_bands_are_accept_clarify_refuse() -> None:
    policy = ConfidencePolicy(accept_at=0.7, clarify_at=0.4)

    assert policy.decide(proposal(0.71)) is ConfidenceDecision.ACCEPT
    assert policy.decide(proposal(0.55)) is ConfidenceDecision.CLARIFY
    assert policy.decide(proposal(0.10)) is ConfidenceDecision.REFUSE


def test_the_thresholds_are_inclusive() -> None:
    policy = ConfidencePolicy(accept_at=0.7, clarify_at=0.4)

    assert policy.decide(proposal(0.7)) is ConfidenceDecision.ACCEPT
    assert policy.decide(proposal(0.4)) is ConfidenceDecision.CLARIFY


def test_the_observed_failure_case_does_not_run() -> None:
    # A real model, asked something no tool could do, invented a call and
    # rated it 0.5. Whatever else these numbers become, that must not execute.
    assert ConfidencePolicy().decide(proposal(0.5)) is not ConfidenceDecision.ACCEPT


def test_thresholds_are_configurable() -> None:
    # They will move once make eval can measure them.
    trusting = ConfidencePolicy(accept_at=0.3, clarify_at=0.2)

    assert trusting.decide(proposal(0.5)) is ConfidenceDecision.ACCEPT


def test_an_inverted_pair_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="clarify_at"):
        ConfidencePolicy(accept_at=0.4, clarify_at=0.7)
