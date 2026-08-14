"""The name E.V. answers to, on disk.

`wake.json`, beside the journal, holding the word, any extra spellings the
microphone actually produces, and whether the loop is running at all. A file
rather than a constant because the name is the user's: this is E.V., and it
could as easily be Ana's assistant answering to something else.

Off unless the file says otherwise. Always-on listening is a decision somebody
makes, not a default they discover.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ev.application.wake import WakeWord

WAKE_FILE = "wake.json"


def wake_path(state_dir: Path) -> Path:
    return state_dir / WAKE_FILE


def load_wake(path: Path) -> WakeWord:
    if not path.exists():
        return WakeWord()

    payload = json.loads(path.read_text(encoding="utf-8"))
    word = str(payload.get("word", "ev")).strip()
    if not word:
        raise ValueError(f"{path}: 'word' cannot be empty")

    also = payload.get("also", [])
    if not isinstance(also, list):
        raise ValueError(f"{path}: 'also' must be a list of spellings")

    return WakeWord(
        word=word,
        also=tuple(str(spelling) for spelling in also),
        enabled=bool(payload.get("enabled", False)),
    )


def save_wake(path: Path, wake: WakeWord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"word": wake.word, "also": list(wake.also), "enabled": wake.enabled}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def reloader(path: Path) -> Callable[[], WakeWord | None]:
    """Watches the file, and reports only when it has changed.

    The same shape as the grants and the application levels, for the same
    reason: someone who renames E.V. and watches the next word go unanswered
    has been told their decision does not count until they restart something.
    """
    seen: list[float] = []

    def fresh() -> WakeWord | None:
        try:
            stamp = path.stat().st_mtime
        except OSError:
            return None

        if seen and seen[0] == stamp:
            return None

        seen.clear()
        seen.append(stamp)
        try:
            return load_wake(path)
        except ValueError:
            # A broken file is reported by `ev --wake`, and must not leave the
            # microphone running against a name nobody can read.
            return None

    return fresh
