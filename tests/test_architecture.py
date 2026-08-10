"""Structural invariants from CLAUDE.md, checked as tests.

`ev/infrastructure/` is the only layer allowed to touch the outside world.
Everything above it is pure by construction, so a stray import is a defect
rather than a style question.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PURE_LAYERS = ("ev/domain", "ev/application", "ev/router")

FORBIDDEN = frozenset(
    {
        "asyncio.subprocess",
        "http",
        "httpx",
        "requests",
        "shutil",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
)


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _is_forbidden(name: str) -> bool:
    parts = name.split(".")
    return any(".".join(parts[:i]) in FORBIDDEN for i in range(1, len(parts) + 1))


def test_pure_layers_exist() -> None:
    for layer in PURE_LAYERS:
        assert (ROOT / layer).is_dir(), f"missing layer: {layer}"


def test_pure_layers_do_not_touch_the_outside_world() -> None:
    offenders: list[str] = []
    for layer in PURE_LAYERS:
        for path in sorted((ROOT / layer).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            offenders.extend(
                f"{path.relative_to(ROOT)} imports {name}"
                for name in sorted(_imported_names(tree))
                if _is_forbidden(name)
            )
    assert offenders == []
