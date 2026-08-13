"""What the user has said about each application.

One file, `applications.json`, beside the journal. It is the user's answer and
nothing else writes to it without them saying so: a level is set by hand, by
`ev --apps`, or by answering "always" to a question the panel asked.

An application nobody has decided about is `ask`. Not `open`, which would let
E.V. act on something the user never considered; not `blocked`, which would
mean nothing works until a file is edited, and a security control people have
to fight is a security control people turn off.

Read per turn, like the permission grants, for the same reason: someone who
changes a level and watches the next turn ignore it has been told their
decision does not count.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path

from ev.domain.access import AccessLevel

APPLICATIONS_FILE = "applications.json"

DEFAULT = AccessLevel.ASK
"""What an application nobody has decided about gets."""

VERIFIED_FOR = timedelta(minutes=5)
"""How long one verification covers, for the same application.

`verify` means "prove it is you", not "prove it is you once per keystroke".
Playing an album, skipping a track and pausing it are one intent, and asking
three times for a fingerprint teaches people to authenticate without reading,
which is the habit the prompt exists to interrupt.

Five minutes is `sudo`'s figure and the ceiling macOS itself puts on reusing a
recent Touch ID. It is a window, not a session: it does not renew on use, so a
long afternoon of asking is a fresh prompt every five minutes rather than one
at the start.
"""


def applications_path(state_dir: Path) -> Path:
    return state_dir / APPLICATIONS_FILE


def key(name: str) -> str:
    """The name, folded. `Visual Studio Code` and `visual studio code` are the
    same application, and a level that depends on capitalisation is a level
    that silently stops applying."""
    return name.strip().casefold()


def load_levels(path: Path) -> dict[str, AccessLevel]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    applications = payload.get("applications", {})
    if not isinstance(applications, dict):
        raise ValueError(f"{path}: 'applications' must be a map of name to level")

    levels: dict[str, AccessLevel] = {}
    for name, level in applications.items():
        try:
            levels[key(str(name))] = AccessLevel(str(level))
        except ValueError:
            known = ", ".join(item.value for item in AccessLevel)
            # A typo is an error rather than something to skip: silently
            # ignoring it leaves someone believing they blocked an application
            # they did not.
            raise ValueError(
                f"{path}: {name} has no level {level!r}. Known: {known}"
            ) from None
    return levels


def save_levels(path: Path, levels: Mapping[str, AccessLevel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "applications": {name: level.value for name, level in sorted(levels.items())}
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def reloader(path: Path) -> Callable[[], dict[str, AccessLevel] | None]:
    """Watches the levels file, and reports only when it has changed.

    One `stat` per turn, and a read only when the modification time moves. The
    same shape as the permission grants, and for the same reason: a level
    someone changed has to count on the next turn, not on the next restart.
    """
    seen: list[float] = []

    def fresh() -> dict[str, AccessLevel] | None:
        try:
            stamp = path.stat().st_mtime
        except OSError:
            # Deleted, or never written. Nothing to report; the ledger keeps
            # what it has, and the default covers what it does not.
            return None

        if seen and seen[0] == stamp:
            return None

        seen.clear()
        seen.append(stamp)
        try:
            return load_levels(path)
        except ValueError:
            # A broken file is reported by `ev --apps`, and must not make every
            # application unreachable in the meantime.
            return None

    return fresh


class ApplicationLedger:
    """The levels, re-read when the file changes."""

    def __init__(
        self,
        levels: Mapping[str, AccessLevel] | None = None,
        *,
        default: AccessLevel = DEFAULT,
        refresh: Callable[[], Mapping[str, AccessLevel] | None] | None = None,
        persist: Callable[[Mapping[str, AccessLevel]], None] | None = None,
    ) -> None:
        self._levels = dict(levels or {})
        self._default = default
        self._refresh = refresh
        self._persist = persist
        # In memory only, and per application. A window that survived a
        # restart would be a window nobody watched open.
        self._verified: dict[str, datetime] = {}

    def _reload(self) -> None:
        if self._refresh is None:
            return
        fresh = self._refresh()
        if fresh is not None:
            self._levels = dict(fresh)

    def level(self, application: str | None) -> AccessLevel:
        """What E.V. may do with this application.

        `None` -- a tool that touches no application at all -- is `OPEN`: there
        is nothing here to have an opinion about, and the tool's own risk and
        permissions still apply.
        """
        if application is None:
            return AccessLevel.OPEN

        self._reload()
        return self._levels.get(key(application), self._default)

    def verified(self, application: str, at: datetime | None = None) -> None:
        """The owner just proved who they are, for this application."""
        self._verified[key(application)] = at or datetime.now()

    def recently_verified(self, application: str, now: datetime | None = None) -> bool:
        when = self._verified.get(key(application))
        if when is None:
            return False
        return (now or datetime.now()) - when < VERIFIED_FOR

    def forget_verification(self, application: str) -> None:
        """Used when a level changes: a window opened under the old level says
        nothing about the new one."""
        self._verified.pop(key(application), None)

    def remember(self, application: str, level: AccessLevel) -> None:
        """Write down an answer the user just gave."""
        self._reload()
        self._levels[key(application)] = level
        self.forget_verification(application)
        if self._persist is not None:
            self._persist(self._levels)

    def known(self) -> dict[str, AccessLevel]:
        self._reload()
        return dict(self._levels)
