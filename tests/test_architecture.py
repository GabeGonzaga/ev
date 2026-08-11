"""Structural invariants from CLAUDE.md, checked as tests.

`ev/infrastructure/` is the only layer allowed to touch the outside world.
Everything above it is pure by construction, so a stray import is a defect
rather than a style question.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PURE_LAYERS = ("ev/domain", "ev/application", "ev/router", "ev/registry.py")

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


SHELL_APIS = frozenset(
    {
        "create_subprocess_shell",
        "system",
        "popen",
        "check_output",
        "getoutput",
    }
)


def _sources(layer: str) -> list[Path]:
    path = ROOT / layer
    return sorted(path.rglob("*.py")) if path.is_dir() else [path]


def test_pure_layers_exist() -> None:
    for layer in PURE_LAYERS:
        assert (ROOT / layer).exists(), f"missing layer: {layer}"


def test_pure_layers_do_not_touch_the_outside_world() -> None:
    offenders: list[str] = []
    for layer in PURE_LAYERS:
        for path in _sources(layer):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            offenders.extend(
                f"{path.relative_to(ROOT)} imports {name}"
                for name in sorted(_imported_names(tree))
                if _is_forbidden(name)
            )
    assert offenders == []


def test_adapters_never_assemble_the_text_they_send() -> None:
    # An AppleScript source is a constant and values travel as argv. A source
    # built with an f-string is one interpolation away from an album name
    # becoming a program, so the adapters do not build strings at all.
    sources = [ROOT / "ev" / "infrastructure" / "macos" / "applescript.py"]
    sources += sorted((ROOT / "ev" / "capabilities").rglob("adapters.py"))

    offenders: list[str] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            where = f"{path.relative_to(ROOT)}"
            if isinstance(node, ast.JoinedStr):
                offenders.append(f"{where} builds an f-string")
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                offenders.append(f"{where} uses % formatting")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"format", "join", "replace"}
            ):
                offenders.append(f"{where} calls .{node.func.attr}()")
    assert offenders == []


def test_nothing_anywhere_reaches_a_shell() -> None:
    # Invariant 3: there is no run_shell tool, and there is no shell under one
    # either. ProcessRunner takes argv, so a tool argument cannot become a
    # command line.
    offenders: list[str] = []
    for path in sorted((ROOT / "ev").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in SHELL_APIS:
                offenders.append(f"{path.relative_to(ROOT)} calls {node.attr}")
            elif isinstance(node, ast.keyword) and node.arg == "shell":
                offenders.append(f"{path.relative_to(ROOT)} passes shell=")
    assert offenders == []
