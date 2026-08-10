"""The one door.

All tool execution goes through `Registry.call()` (CLAUDE.md, invariant 4).
There is no second path, and nothing downstream of here ever sees raw router
output: arguments are validated against the tool's Pydantic model first, and
the handler receives the model instance, not a dict.

The registry depends on three ports it does not implement -- the permission
policy, the confirmation surface and the journal. They are Protocols, so the
CLI, the tests and later the IPC layer each supply their own without the
registry knowing which is which. All three are required: there is no default,
because every sensible default here is a permissive one.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ev.application.confirmation import ConfirmationRequest
from ev.application.policy import PolicyDecision
from ev.domain.permissions import Permission
from ev.domain.results import ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
"""`capability.tool`. The name is an identifier, so it is constrained like one."""


@dataclass(frozen=True, slots=True)
class ToolSpec[ArgsT: BaseModel]:
    """A tool declaration. Declaration only -- the logic lives in `service.py`."""

    name: str
    description: str
    args: type[ArgsT]
    """The single source of truth for validation and for the generated LLM spec."""

    risk: RiskLevel
    handler: Callable[[ArgsT], Awaitable[ToolResult]]
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    @property
    def capability(self) -> str:
        return self.name.split(".", 1)[0]


class CallRecord(BaseModel):
    """One line of the audit trail, handed to the journal port."""

    model_config = ConfigDict(frozen=True)

    tool: str
    risk: RiskLevel
    arguments: dict[str, object] = Field(default_factory=dict)
    """Validated and normalised, except when validation is what failed."""

    result: ToolResult
    urgent: bool
    """Destructive actions are flushed now, not batched (invariant 5)."""


class PermissionPolicy(Protocol):
    def decide(self, spec: ToolSpec[Any]) -> PolicyDecision: ...


class Confirmation(Protocol):
    async def confirm(self, request: ConfirmationRequest) -> bool: ...


class Journal(Protocol):
    async def record(self, record: CallRecord) -> None: ...


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '(root)'}: {item['msg']}"
        for item in error.errors()
    )


class Registry:
    def __init__(
        self,
        *,
        policy: PermissionPolicy,
        confirmation: Confirmation,
        journal: Journal,
    ) -> None:
        self._tools: dict[str, ToolSpec[Any]] = {}
        self._policy = policy
        self._confirmation = confirmation
        self._journal = journal

    def register(self, spec: ToolSpec[Any]) -> None:
        if not TOOL_NAME.match(spec.name):
            raise ValueError(f"tool name must be capability.tool: {spec.name!r}")
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def tools(self) -> list[ToolSpec[Any]]:
        return [self._tools[name] for name in sorted(self._tools)]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def specs(self) -> list[dict[str, object]]:
        """The tool specs handed to the model. Generated, never hand-written:
        the args model is the schema, so the two cannot drift."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.args.model_json_schema(),
                },
            }
            for spec in self.tools()
        ]

    def manifest(self) -> dict[str, object]:
        """What E.V. can do, by capability, with the risk and permissions it
        carries. This is the honest answer to "what does this thing control"."""
        capabilities: dict[str, list[dict[str, object]]] = {}
        for spec in self.tools():
            capabilities.setdefault(spec.capability, []).append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "risk": spec.risk.value,
                    "permissions": sorted(item.value for item in spec.permissions),
                }
            )
        return {"capabilities": capabilities}

    async def call(self, name: str, arguments: Mapping[str, object]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            # Not journalled: nothing ran, and there is no tool to attribute it
            # to. A router proposing a name that does not exist is a routing
            # failure, which the evals measure, not an action on the machine.
            return ToolResult.failure(
                name, ToolErrorCode.UNKNOWN_TOOL, f"unknown tool: {name}"
            )

        raw = dict(arguments)
        try:
            validated = spec.args.model_validate(raw)
        except ValidationError as error:
            return await self._finish(
                spec,
                raw,
                ToolResult.failure(
                    spec.name, ToolErrorCode.INVALID_ARGUMENTS, _describe(error)
                ),
            )

        normalised: dict[str, object] = validated.model_dump(mode="json")

        decision = self._policy.decide(spec)
        if decision is PolicyDecision.DENY:
            return await self._finish(
                spec,
                normalised,
                ToolResult.failure(
                    spec.name,
                    ToolErrorCode.PERMISSION_DENIED,
                    f"policy denied {spec.name}",
                ),
            )

        # Invariant 5 is enforced here rather than delegated to the policy, so
        # that a policy bug cannot make a destructive action run unconfirmed.
        if decision is PolicyDecision.CONFIRM or spec.risk is RiskLevel.DESTRUCTIVE:
            request = ConfirmationRequest(
                tool=spec.name, risk=spec.risk, arguments=normalised
            )
            if not await self._confirmation.confirm(request):
                return await self._finish(
                    spec,
                    normalised,
                    ToolResult.failure(
                        spec.name,
                        ToolErrorCode.CONFIRMATION_DECLINED,
                        f"user declined {spec.name}",
                    ),
                )

        try:
            result = await spec.handler(validated)
        except Exception as error:  # the adapter boundary, not a bare except
            result = ToolResult.failure(
                spec.name,
                ToolErrorCode.ADAPTER_FAILED,
                str(error) or type(error).__name__,
            )

        if result.tool != spec.name:
            # The door owns the attribution, so the journal stays trustworthy.
            result = result.model_copy(update={"tool": spec.name})

        return await self._finish(spec, normalised, result)

    async def _finish(
        self,
        spec: ToolSpec[Any],
        arguments: dict[str, object],
        result: ToolResult,
    ) -> ToolResult:
        # A journal failure is not swallowed: an action that ran without being
        # recorded is a defect, and the flush semantics are step 5's decision.
        await self._journal.record(
            CallRecord(
                tool=spec.name,
                risk=spec.risk,
                arguments=arguments,
                result=result,
                urgent=spec.risk is RiskLevel.DESTRUCTIVE,
            )
        )
        return result
