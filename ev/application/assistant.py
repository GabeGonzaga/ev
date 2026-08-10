"""One turn: an utterance in, a result out.

Phase 0 has one router. The phase 1 seam is the `None` branch below -- the
model router returns the same `Resolution`, so tier 2 becomes one more line
here and nothing else changes.
"""

from __future__ import annotations

from ev.domain.results import ToolResult
from ev.registry import Registry
from ev.router.static import StaticRouter


class Assistant:
    def __init__(self, router: StaticRouter, registry: Registry) -> None:
        self._router = router
        self._registry = registry

    async def handle(self, utterance: str) -> ToolResult | None:
        """`None` when nothing routed -- the same meaning the router gives it.

        It is not a failed call: no tool was chosen, so there is nothing to
        report a failure about. In phase 1 the model router runs before this
        returns, and what survives it becomes a clarifying question.
        """
        resolution = self._router.resolve(utterance)
        if resolution is None:
            return None

        return await self._registry.call(resolution.tool, resolution.arguments)
