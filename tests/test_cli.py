from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from ev.cli import (
    EXIT_FAILED,
    EXIT_NOT_UNDERSTOOD,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    EXIT_UNSURE,
    ConsoleConfirmation,
    build,
    main,
)
from ev.domain.permissions import Permission, PermissionState
from ev.infrastructure.ollama.client import OllamaUnavailable
from tests.conftest import FakeBin


class Declining:
    """A model that says "none of these", which is most of the suite."""

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str:
        return json.dumps({"tool": None, "arguments": {}, "confidence": 0.0})


class Proposing:
    def __init__(self, tool: str, arguments: dict[str, Any], confidence: float) -> None:
        self.payload = {
            "tool": tool,
            "arguments": arguments,
            "confidence": confidence,
        }

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str:
        return json.dumps(self.payload)


class Unreachable:
    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str:
        raise OllamaUnavailable("http://127.0.0.1:11434")


def journal_rows(database: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute("SELECT * FROM journal ORDER BY id").fetchall()
    finally:
        connection.close()


# --- read-only views ------------------------------------------------------


def test_specs_are_json_and_name_the_tools(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--specs"]) == EXIT_OK

    specs = json.loads(capsys.readouterr().out)

    assert [spec["function"]["name"] for spec in specs] == [
        "browser.open_url",
        "language.translate",
        "macro.run",
        "music.control",
        "music.play",
        "music.volume",
    ]


def test_the_manifest_reports_risk_and_permissions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--manifest"]) == EXIT_OK

    manifest = json.loads(capsys.readouterr().out)

    assert manifest["capabilities"]["browser"] == [
        {
            "name": "browser.open_url",
            "description": "Open an http or https URL in the default browser.",
            "risk": "safe",
            "permissions": [],
        }
    ]


def test_the_read_only_views_touch_no_database(tmp_path: Path) -> None:
    # They execute nothing, so they must not create the user's database as a
    # side effect of being asked what E.V. can do.
    main(["--specs"])

    assert list(tmp_path.iterdir()) == []


# --- one turn -------------------------------------------------------------


def test_an_utterance_runs_and_is_journalled(
    tmp_path: Path, fake_bin: FakeBin, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "ev.db"

    assert main(["--database", str(database), "open github.com"]) == EXIT_OK

    assert capsys.readouterr().out.strip() == "Opening github.com"
    assert fake_bin.argv() == ["--", "https://github.com/"]

    (row,) = journal_rows(database)
    assert row["tool"] == "browser.open_url"
    assert row["ok"] == 1


def test_the_journal_is_flushed_before_exit(tmp_path: Path, fake_bin: FakeBin) -> None:
    # The journal batches. Without a flush on the way out, a single-shot run
    # would record nothing at all.
    database = tmp_path / "ev.db"

    main(["--database", str(database), "open github.com"])

    assert len(journal_rows(database)) == 1


def test_words_do_not_need_quoting(tmp_path: Path, fake_bin: FakeBin) -> None:
    database = tmp_path / "ev.db"

    assert main(["--database", str(database), "open", "github.com"]) == EXIT_OK

    assert fake_bin.argv() == ["--", "https://github.com/"]


def test_an_unrouted_utterance_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--database", str(tmp_path / "ev.db"), "empty the trash"], Declining())

    assert code == EXIT_NOT_UNDERSTOOD
    assert "did not understand" in capsys.readouterr().err


def test_a_failing_tool_reports_on_stderr(
    tmp_path: Path,
    fake_bin: FakeBin,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv("EV_FAKE_STDERR", "nothing can open that")
    database = tmp_path / "ev.db"

    code = main(["--database", str(database), "open github.com"])

    assert code == EXIT_FAILED
    assert "nothing can open that" in capsys.readouterr().err
    assert journal_rows(database)[0]["ok"] == 0


def test_no_utterance_is_not_an_error_message_about_tools(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--database", str(tmp_path / "ev.db")])

    assert code == EXIT_NOT_UNDERSTOOD
    assert "--repl" in capsys.readouterr().err


# --- repl -----------------------------------------------------------------


def test_the_repl_handles_lines_until_eof(
    tmp_path: Path,
    fake_bin: FakeBin,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = iter(["open github.com", "open example.com"])

    def fake_input(prompt: str = "") -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)
    database = tmp_path / "ev.db"

    assert main(["--database", str(database), "--repl"], Declining()) == EXIT_OK

    assert "Opening github.com" in capsys.readouterr().out
    assert len(journal_rows(database)) == 2


def test_the_repl_keeps_going_after_a_bad_turn(
    tmp_path: Path,
    fake_bin: FakeBin,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = iter(["empty the trash", "open github.com"])

    def fake_input(prompt: str = "") -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)

    assert (
        main(["--database", str(tmp_path / "ev.db"), "--repl"], Declining()) == EXIT_OK
    )

    captured = capsys.readouterr()
    assert "did not understand" in captured.err
    assert "Opening github.com" in captured.out


# --- tier 2 -----------------------------------------------------------------


def test_a_confident_model_proposal_runs(
    tmp_path: Path, fake_bin: FakeBin, capsys: pytest.CaptureFixture[str]
) -> None:
    # Nothing in the static router matches this phrasing.
    model = Proposing("browser.open_url", {"url": "https://github.com"}, 0.9)

    code = main(["--database", str(tmp_path / "ev.db"), "pull up that git site"], model)

    assert code == EXIT_OK
    assert fake_bin.argv() == ["--", "https://github.com/"]


def test_a_middling_proposal_asks_instead_of_acting(
    tmp_path: Path, fake_bin: FakeBin, capsys: pytest.CaptureFixture[str]
) -> None:
    # 0.5 is the number a real model gave an invented call. It must not run.
    model = Proposing("music.play", {"name": "Capitals of Portugal"}, 0.5)

    code = main(["--database", str(tmp_path / "ev.db"), "what is the capital"], model)

    assert code == EXIT_UNSURE
    assert "Did you mean" in capsys.readouterr().err
    assert not fake_bin.was_run()


def test_a_poor_proposal_is_refused_outright(
    tmp_path: Path, fake_bin: FakeBin, capsys: pytest.CaptureFixture[str]
) -> None:
    model = Proposing("music.play", {"name": "whatever"}, 0.2)

    code = main(["--database", str(tmp_path / "ev.db"), "mumble mumble"], model)

    assert code == EXIT_NOT_UNDERSTOOD
    assert not fake_bin.was_run()


def test_an_unreachable_model_is_reported_as_such(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # "I did not understand that" would be a lie: nothing was asked of it.
    code = main(["--database", str(tmp_path / "ev.db"), "mumble mumble"], Unreachable())

    assert code == EXIT_UNAVAILABLE
    assert "Is it running" in capsys.readouterr().err


def test_a_static_hit_never_reaches_the_model(
    tmp_path: Path, fake_bin: FakeBin
) -> None:
    class Exploding:
        async def complete(
            self, messages: list[dict[str, str]], *, schema: dict[str, Any]
        ) -> str:  # pragma: no cover
            raise AssertionError("tier 1 answered; the model must not be called")

    assert (
        main(["--database", str(tmp_path / "ev.db"), "open github.com"], Exploding())
        == EXIT_OK
    )


def test_the_model_flag_repoints_every_role(tmp_path: Path) -> None:
    database = tmp_path / "ev.db"

    application = build(database=database, model="llama3.1:8b", completion=Declining())

    assert application.settings.models() == ["llama3.1:8b"]


def test_speak_says_the_answer_out_loud(tmp_path: Path, fake_bin: FakeBin) -> None:
    database = tmp_path / "ev.db"

    assert main(["--database", str(database), "--speak", "abre example.com"]) == EXIT_OK

    # Two processes ran: open(1) did the work, say(1) reported it.
    runs = fake_bin.runs()
    assert [run[0] for run in runs] == ["open", "say"]
    assert runs[1][1:] == ["--", "Opening example.com"]


def test_the_locale_chooses_the_voice_and_the_words(
    tmp_path: Path, fake_bin: FakeBin
) -> None:
    # The gap this closed: Joana used to read "Opening example.com". A
    # Portuguese voice reading English words is worse than either alone.
    main(
        [
            "--database",
            str(tmp_path / "ev.db"),
            "--speak",
            "--locale",
            "pt-PT",
            "abre example.com",
        ]
    )

    assert fake_bin.runs()[1] == ["say", "-v", "Joana", "--", "A abrir example.com"]


def test_without_speak_nothing_is_said(tmp_path: Path, fake_bin: FakeBin) -> None:
    # Speaking is opt-in on the CLI. A terminal that talks unbidden is a
    # surprise, and the native host is what speaks in the application.
    main(["--database", str(tmp_path / "ev.db"), "abre example.com"])

    assert [run[0] for run in fake_bin.runs()] == ["open"]


# --- confirmation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_a_non_interactive_stdin_declines(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A pipe is not consent.
    from ev.application.confirmation import ConfirmationRequest
    from ev.domain.risk import RiskLevel

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    granted = await ConsoleConfirmation().confirm(
        ConfirmationRequest(
            tool="system.empty_trash", risk=RiskLevel.DESTRUCTIVE, arguments={}
        )
    )

    assert granted is False


# --- asserted permissions -------------------------------------------------


def test_grant_records_the_permission_and_says_what_it_does_not_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--database", str(tmp_path / "ev.db"), "--grant", "apple_events"])

    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert captured.out.strip() == "apple_events"
    assert "grants nothing" in captured.err
    assert json.loads((tmp_path / "permissions.json").read_text()) == {
        "granted": ["apple_events"]
    }


def test_a_grant_is_loaded_on_the_next_run(tmp_path: Path) -> None:
    database = tmp_path / "ev.db"
    main(["--database", str(database), "--grant", "apple_events"])

    application = build(database=database)

    assert application.ledger.state(Permission.APPLE_EVENTS) is PermissionState.GRANTED
    assert application.ledger.state(Permission.CAMERA) is PermissionState.UNDETERMINED


def test_revoke_undoes_a_grant(tmp_path: Path) -> None:
    database = tmp_path / "ev.db"
    main(["--database", str(database), "--grant", "apple_events"])
    main(["--database", str(database), "--revoke", "apple_events"])

    application = build(database=database)

    assert (
        application.ledger.state(Permission.APPLE_EVENTS)
        is PermissionState.UNDETERMINED
    )


def test_an_unknown_permission_is_refused_with_the_known_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--database", str(tmp_path / "ev.db"), "--grant", "mic"])

    assert code == EXIT_FAILED
    assert "microphone" in capsys.readouterr().err
    assert not (tmp_path / "permissions.json").exists()


def test_granting_runs_no_tool(tmp_path: Path, fake_bin: FakeBin) -> None:
    main(["--database", str(tmp_path / "ev.db"), "--grant", "apple_events"])

    assert not fake_bin.was_run()
