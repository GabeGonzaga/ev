"""One turn: an utterance in, one of three outcomes out.

    ToolResult     something ran, well or badly
    Clarification  E.V. has a guess it is not sure enough to act on
    None           nothing routed at all

The tiers are tried in order and cost in that order too: tier 0 and tier 1 are
microseconds and answer at confidence 1.0, tier 2 is a model call. A static hit
never reaches the model -- that is the point of having tiers, not a shortcut.
"""

from __future__ import annotations

from ev.application.policy import ConfidenceDecision, ConfidencePolicy
from ev.domain.resolution import Resolution
from ev.domain.results import Clarification, ToolResult
from ev.registry import Registry
from ev.router.model import ModelRouter
from ev.router.static import StaticRouter


class Assistant:
    def __init__(
        self,
        router: StaticRouter,
        registry: Registry,
        *,
        model_router: ModelRouter | None = None,
        confidence: ConfidencePolicy | None = None,
    ) -> None:
        self._router = router
        self._registry = registry
        self._model_router = model_router
        self._confidence = confidence or ConfidencePolicy()

    async def handle(self, utterance: str) -> ToolResult | Clarification | None:
        resolution = self._router.resolve(utterance)
        if resolution is not None:
            return await self._registry.call(resolution.tool, resolution.arguments)

        if self._model_router is None:
            return None

        proposal = await self._model_router.resolve(utterance)
        if proposal is None:
            return None

        decision = self._confidence.decide(proposal)
        if decision is ConfidenceDecision.REFUSE:
            # Not "no". "I am not going to act on a guess this poor", which
            # from the outside is the same as not having understood.
            return None
        if decision is ConfidenceDecision.CLARIFY:
            return _asking(proposal)

        return await self._registry.call(proposal.tool, proposal.arguments)


def _asking(proposal: Resolution) -> Clarification:
    return Clarification(
        tool=proposal.tool,
        arguments=dict(proposal.arguments),
        confidence=proposal.confidence,
        response=proposal.response,
    )
