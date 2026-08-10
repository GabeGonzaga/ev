from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.capabilities.browser.adapters import OpenAdapter
from ev.capabilities.browser.args import OpenUrlArgs
from ev.capabilities.browser.service import BrowserService
from ev.capabilities.browser.tools import browser_tools
from ev.domain.results import ToolErrorCode
from ev.domain.risk import RiskLevel
from ev.infrastructure.macos.processes import ProcessRunner
from ev.registry import CallRecord, Registry
from tests.conftest import FakeBin


class CollectingJournal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class RefusingConfirmation:
    """Nothing in this capability may need confirming."""

    async def confirm(self, request: object) -> bool:  # pragma: no cover
        raise AssertionError("browser.open_url must not require confirmation")


def build() -> tuple[Registry, CollectingJournal]:
    service = BrowserService(OpenAdapter(ProcessRunner()))
    journal = CollectingJournal()
    registry = Registry(
        policy=PermissionPolicy(PermissionLedger()),
        confirmation=RefusingConfirmation(),
        journal=journal,
    )
    for spec in browser_tools(service):
        registry.register(spec)
    return registry, journal


# --- arguments ------------------------------------------------------------


def test_only_http_and_https_are_accepted() -> None:
    # open(1) dispatches any registered scheme. The args model is what stops
    # the router selecting a target outside the browser.
    for rejected in (
        "file:///etc/passwd",
        "mailto:someone@a.test",
        "x-apple-shortcuts://run-shortcut?name=Wipe",
        "javascript:alert(1)",
        "not a url",
    ):
        # model_validate, because a dict from the router is what the registry
        # actually hands to this model.
        with pytest.raises(ValidationError):
            OpenUrlArgs.model_validate({"url": rejected})


def test_unknown_fields_are_refused() -> None:
    with pytest.raises(ValidationError):
        OpenUrlArgs.model_validate({"url": "https://a.test", "background": True})


# --- the adapter boundary -------------------------------------------------


@pytest.mark.asyncio
async def test_the_adapter_builds_the_exact_argv(fake_bin: FakeBin) -> None:
    await OpenAdapter(ProcessRunner()).open_url("https://a.test/x?y=1")

    assert fake_bin.argv() == ["--", "https://a.test/x?y=1"]


@pytest.mark.asyncio
async def test_a_url_that_looks_like_a_flag_stays_a_url(fake_bin: FakeBin) -> None:
    # "--" is why this is a URL and not an option to open(1).
    await OpenAdapter(ProcessRunner()).open_url("https://a.test/--background")

    assert fake_bin.argv() == ["--", "https://a.test/--background"]


# --- the whole chain ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_call_runs_end_to_end(fake_bin: FakeBin) -> None:
    registry, journal = build()

    result = await registry.call("browser.open_url", {"url": "https://a.test"})

    assert result.ok
    assert result.speech == "Opening a.test"
    assert fake_bin.argv() == ["--", "https://a.test/"]
    assert journal.records[0].risk is RiskLevel.SAFE
    assert journal.records[0].urgent is False


@pytest.mark.asyncio
async def test_a_rejected_url_never_reaches_the_process(fake_bin: FakeBin) -> None:
    registry, journal = build()

    result = await registry.call("browser.open_url", {"url": "file:///etc/passwd"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert not fake_bin.was_run()
    assert journal.records[0].arguments == {"url": "file:///etc/passwd"}


@pytest.mark.asyncio
async def test_a_failing_open_becomes_a_typed_failure(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv("EV_FAKE_STDERR", "no application knows how to open that")
    registry, _ = build()

    result = await registry.call("browser.open_url", {"url": "https://a.test"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED
    assert "no application knows how to open that" in result.error.message


# --- declaration ----------------------------------------------------------


def test_the_tool_declares_no_permission_it_does_not_need() -> None:
    service = BrowserService(OpenAdapter(ProcessRunner()))

    (spec,) = browser_tools(service)

    assert spec.permissions == frozenset()
    assert spec.risk is RiskLevel.SAFE
