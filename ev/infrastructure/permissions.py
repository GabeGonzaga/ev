"""What the user has asserted about TCC permissions, until a host can report it.

This grants nothing. macOS decides whether an Apple Event is delivered, and it
will still prompt or refuse regardless of what is in this file. What the file
does is stop E.V. refusing *first*, on its own, before the system gets a say --
which is what happens in phase 0, where `PermissionLedger` reports
`UNDETERMINED` for everything and ADR 0003 denies on unknown state.

It is the user's own statement about their machine, written down explicitly.
When the signed native host lands in phase 1.5 it reports the real state and
this becomes a fallback for a host that is not running.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path

from ev.domain.permissions import Permission, PermissionState

GRANTS_FILE = "permissions.json"


def grants_path(state_dir: Path) -> Path:
    return state_dir / GRANTS_FILE


def parse_permission(name: str) -> Permission:
    try:
        return Permission(name)
    except ValueError:
        known = ", ".join(permission.value for permission in Permission)
        raise ValueError(f"unknown permission {name!r}. Known: {known}") from None


def load_grants(path: Path) -> dict[Permission, PermissionState]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    granted = payload.get("granted", [])
    if not isinstance(granted, list):
        raise ValueError(f"{path}: 'granted' must be a list of permission names")

    try:
        # A typo is an error, not something to skip: silently ignoring it
        # leaves the user believing they asserted something they did not.
        return {parse_permission(name): PermissionState.GRANTED for name in granted}
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from None


def reloader(
    path: Path,
) -> Callable[[], dict[Permission, PermissionState] | None]:
    """Watches the grants file, and reports only when it has changed.

    Cheap enough to consult on every decision: one `stat`, and a read only
    when the modification time moves. The alternative was telling people to
    restart a daemon after granting, which is the kind of instruction that
    gets left out of the message and discovered an hour later.
    """
    seen: list[float] = []

    def read() -> dict[Permission, PermissionState] | None:
        try:
            stamp = path.stat().st_mtime
        except OSError:
            return None

        if seen and seen[0] == stamp:
            return None

        seen.clear()
        seen.append(stamp)
        try:
            return load_grants(path)
        except ValueError:
            # A malformed file is not a reason to forget what was already
            # granted; it is reported when the CLI reads it.
            return None

    return read


def save_grants(path: Path, permissions: Iterable[Permission]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"granted": sorted({permission.value for permission in permissions})}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
