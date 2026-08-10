from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from ev.application.confirmation import ConfirmationRequest
from ev.application.policy import PolicyDecision
from ev.domain.permissions import Permission
from ev.domain.results import ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel
from ev.registry import CallRecord, Registry, ToolSpec


class OpenArgs(BaseModel):
    url: str
    background: bool = False


class FixedPolicy:
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision

    def decide(self, spec: ToolSpec[Any]) -> PolicyDecision:
        return self.decision


class FixedConfirmation:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.requests: list[ConfirmationRequest] = []

    async def confirm(self, request: ConfirmationRequest) -> bool:
        self.requests.append(request)
        return self.answer


class FakeJournal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class Handler:
    """Records what actually reached the adapter boundary."""

    def __init__(
        self, result: ToolResult | None = None, raises: Exception | None = None
    ) -> None:
        self.calls: list[OpenArgs] = []
        self._result = result
        self._raises = raises

    async def __call__(self, args: OpenArgs) -> ToolResult:
        self.calls.append(args)
        if self._raises is not None:
            raise self._raises
        return self._result or ToolResult.success("browser.open_url")


def build(
    handler: Handler,
    *,
    risk: RiskLevel = RiskLevel.SAFE,
    decision: PolicyDecision = PolicyDecision.ALLOW,
    confirms: bool = True,
    name: str = "browser.open_url",
) -> tuple[Registry, FixedConfirmation, FakeJournal]:
    confirmation = FixedConfirmation(confirms)
    journal = FakeJournal()
    registry = Registry(
        policy=FixedPolicy(decision), confirmation=confirmation, journal=journal
    )
    registry.register(
        ToolSpec(
            name=name,
            description="Open a URL in the default browser",
            args=OpenArgs,
            risk=risk,
            handler=handler,
            permissions=frozenset({Permission.APPLE_EVENTS}),
        )
    )
    return registry, confirmation, journal


# --- registration ---------------------------------------------------------


def test_tool_names_must_be_capability_dot_tool() -> None:
    registry = Registry(
        policy=FixedPolicy(PolicyDecision.ALLOW),
        confirmation=FixedConfirmation(True),
        journal=FakeJournal(),
    )
    for bad in ("open_url", "Browser.open", "browser.open.url", "browser."):
        with pytest.raises(ValueError, match=r"capability\.tool"):
            registry.register(
                ToolSpec(
                    name=bad,
                    description="",
                    args=OpenArgs,
                    risk=RiskLevel.SAFE,
                    handler=Handler(),
                )
            )


def test_a_tool_cannot_be_registered_twice() -> None:
    registry, _, _ = build(Handler())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            ToolSpec(
                name="browser.open_url",
                description="",
                args=OpenArgs,
                risk=RiskLevel.SAFE,
                handler=Handler(),
            )
        )


# --- the door -------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_tool_is_refused_and_not_journalled() -> None:
    registry, _, journal = build(Handler())

    result = await registry.call("browser.nope", {"url": "https://a.test"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.UNKNOWN_TOOL
    assert journal.records == []


@pytest.mark.asyncio
async def test_invalid_arguments_never_reach_the_handler() -> None:
    handler = Handler()
    registry, _, journal = build(handler)

    result = await registry.call("browser.open_url", {"wrong": 1})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert handler.calls == []
    # Still journalled: a rejected proposal is part of the audit trail.
    assert journal.records[0].arguments == {"wrong": 1}


@pytest.mark.asyncio
async def test_the_handler_receives_the_validated_model_not_a_dict() -> None:
    handler = Handler()
    registry, _, _ = build(handler)

    await registry.call("browser.open_url", {"url": "https://a.test"})

    assert handler.calls == [OpenArgs(url="https://a.test", background=False)]


@pytest.mark.asyncio
async def test_a_denied_call_does_not_run() -> None:
    handler = Handler()
    registry, _, journal = build(handler, decision=PolicyDecision.DENY)

    result = await registry.call("browser.open_url", {"url": "https://a.test"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED
    assert handler.calls == []
    assert journal.records[0].result.ok is False


@pytest.mark.asyncio
async def test_a_declined_confirmation_does_not_run() -> None:
    handler = Handler()
    registry, _, _ = build(handler, decision=PolicyDecision.CONFIRM, confirms=False)

    result = await registry.call("browser.open_url", {"url": "https://a.test"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.CONFIRMATION_DECLINED
    assert handler.calls == []


@pytest.mark.asyncio
async def test_confirmation_is_asked_with_validated_arguments() -> None:
    registry, confirmation, _ = build(Handler(), decision=PolicyDecision.CONFIRM)

    await registry.call("browser.open_url", {"url": "https://a.test"})

    # The user is asked about the call that would actually execute, defaults
    # filled in -- not about the raw proposal.
    assert confirmation.requests[0].arguments == {
        "url": "https://a.test",
        "background": False,
    }


@pytest.mark.asyncio
async def test_destructive_is_confirmed_even_when_the_policy_allows() -> None:
    # Invariant 5 lives at the door: a policy bug must not be able to let a
    # destructive action through unconfirmed.
    handler = Handler()
    registry, confirmation, _ = build(
        handler, risk=RiskLevel.DESTRUCTIVE, decision=PolicyDecision.ALLOW
    )

    await registry.call("browser.open_url", {"url": "https://a.test"})

    assert len(confirmation.requests) == 1
    assert handler.calls != []


@pytest.mark.asyncio
async def test_safe_tools_are_not_confirmed() -> None:
    registry, confirmation, _ = build(Handler(), risk=RiskLevel.SAFE)

    await registry.call("browser.open_url", {"url": "https://a.test"})

    assert confirmation.requests == []


@pytest.mark.asyncio
async def test_destructive_calls_are_journalled_urgently() -> None:
    registry, _, journal = build(Handler(), risk=RiskLevel.DESTRUCTIVE)

    await registry.call("browser.open_url", {"url": "https://a.test"})

    assert journal.records[0].urgent is True


@pytest.mark.asyncio
async def test_safe_calls_are_not_urgent() -> None:
    registry, _, journal = build(Handler(), risk=RiskLevel.SAFE)

    await registry.call("browser.open_url", {"url": "https://a.test"})

    assert journal.records[0].urgent is False


@pytest.mark.asyncio
async def test_an_adapter_that_raises_becomes_a_typed_failure() -> None:
    registry, _, journal = build(Handler(raises=RuntimeError("osascript exited 1")))

    result = await registry.call("browser.open_url", {"url": "https://a.test"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED
    assert result.error.message == "osascript exited 1"
    assert journal.records[0].result.error is not None


@pytest.mark.asyncio
async def test_the_door_owns_the_attribution() -> None:
    handler = Handler(result=ToolResult.success("something.else"))
    registry, _, journal = build(handler)

    result = await registry.call("browser.open_url", {"url": "https://a.test"})

    assert result.tool == "browser.open_url"
    assert journal.records[0].tool == "browser.open_url"


# --- generated views ------------------------------------------------------


def test_specs_are_generated_from_the_args_model() -> None:
    registry, _, _ = build(Handler())

    (spec,) = registry.specs()

    assert spec["type"] == "function"
    function = spec["function"]
    assert isinstance(function, dict)
    assert function["name"] == "browser.open_url"
    parameters = function["parameters"]
    assert isinstance(parameters, dict)
    assert set(parameters["properties"]) == {"url", "background"}
    assert parameters["required"] == ["url"]


def test_the_manifest_reports_risk_and_permissions_by_capability() -> None:
    registry, _, _ = build(Handler(), risk=RiskLevel.DESTRUCTIVE)

    assert registry.manifest() == {
        "capabilities": {
            "browser": [
                {
                    "name": "browser.open_url",
                    "description": "Open a URL in the default browser",
                    "risk": "destructive",
                    "permissions": ["apple_events"],
                }
            ]
        }
    }
