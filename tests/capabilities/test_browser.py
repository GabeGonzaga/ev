from __future__ import annotations

from typing import cast

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

EXPECTED_WINDOW_SOURCE = """on run argv
\tset theUrl to item 1 of argv
\tset theApp to item 2 of argv
\tset theBounds to {item 3 of argv as integer, item 4 of argv as integer, \u00ac
\t\titem 5 of argv as integer, item 6 of argv as integer}
\tif theApp is "com.google.chrome" then
\t\ttell application "Google Chrome"
\t\t\tactivate
\t\t\tset theWindow to make new window
\t\t\tset URL of active tab of theWindow to theUrl
\t\t\tset bounds of theWindow to theBounds
\t\tend tell
\t\treturn "window"
\telse if theApp is "com.apple.safari" then
\t\ttell application "Safari"
\t\t\tactivate
\t\t\tset theWindow to make new document with properties {URL:theUrl}
\t\t\tset bounds of window 1 to theBounds
\t\tend tell
\t\treturn "window"
\tend if
\treturn ""
end run"""
"""Written out rather than imported: the point of the assertion is that this
exact text is what reaches osascript."""


class Windowing:
    """An adapter that reports whether it was asked for a window."""

    def __init__(self, *, can: bool) -> None:
        self.can = can
        self.windowed: tuple[str, tuple[int, int, int, int]] | None = None
        self.opened: list[str] = []

    async def open_small(self, url: str, where: tuple[int, int, int, int]) -> bool:
        self.windowed = (url, where)
        return self.can

    async def open_url(self, url: str) -> None:
        self.opened.append(url)


@pytest.mark.asyncio
async def test_a_window_is_asked_of_the_browser_not_drawn_by_ev() -> None:
    adapter = Windowing(can=True)
    service = BrowserService(cast(OpenAdapter, adapter))

    result = await service.open_url(
        OpenUrlArgs.model_validate({"url": "https://github.com", "where": "window"})
    )

    assert adapter.windowed is not None
    assert adapter.windowed[0] == "https://github.com/"
    # The browser opened it, so `open(1)` was never needed.
    assert adapter.opened == []
    assert result.data["where"] == "window"


@pytest.mark.asyncio
async def test_a_browser_that_cannot_be_told_gets_a_plain_open() -> None:
    """An unfamiliar browser has an unfamiliar dictionary, so the page still
    opens -- as a tab, and the fallback says so rather than claiming a
    window."""
    adapter = Windowing(can=False)
    service = BrowserService(cast(OpenAdapter, adapter))

    result = await service.open_url(
        OpenUrlArgs.model_validate({"url": "https://github.com", "where": "window"})
    )

    assert adapter.opened == ["https://github.com/"]
    assert result.data["where"] == "tab"


@pytest.mark.asyncio
async def test_a_tab_never_asks_for_a_window() -> None:
    adapter = Windowing(can=True)
    service = BrowserService(cast(OpenAdapter, adapter))

    await service.open_url(OpenUrlArgs.model_validate({"url": "https://github.com"}))

    assert adapter.windowed is None
    assert adapter.opened == ["https://github.com/"]


@pytest.mark.asyncio
async def test_the_window_script_is_exactly_this(fake_bin: FakeBin) -> None:
    from ev.infrastructure.macos.applescript import AppleScriptClient

    adapter = OpenAdapter(ProcessRunner(), AppleScriptClient(ProcessRunner()))

    await adapter.open_small("https://github.com", (900, 60, 1420, 700))

    argv = fake_bin.argv()
    assert argv[1] == EXPECTED_WINDOW_SOURCE
    # The URL and the bounds travel as arguments, never as source.
    assert argv[3] == "https://github.com"
    assert argv[-4:] == ["900", "60", "1420", "700"]


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
