"""Enforces the dependency rule so the layering cannot erode silently.

    cli, api -> engine -> library -> core, llm -> errors, config

A new top-level module must be added to ``ALLOWED`` on purpose, which forces the question
"which layer is this?" at review time.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import simulacrum

PKG = Path(simulacrum.__file__).resolve().parent

ALLOWED: dict[str, set[str]] = {
    "errors": set(),
    "config": set(),
    "_version": set(),
    "core": {"errors"},
    "llm": {"errors", "config"},
    "library": {"core", "llm", "errors"},
    "repository": {"core", "errors"},
    "engine": {"core", "llm", "library", "errors"},
    "api": {"engine", "core", "llm", "repository", "config", "errors", "_version"},
    "cli": {"engine", "api", "core", "llm", "repository", "config", "errors", "_version"},
    "ecosystems": {"core", "llm"},  # bundled sample plugins may use only the public extension points
    "web": set(),
}
ROOT_FILES = {"__init__.py", "__main__.py"}  # the public facade may import anything


def _modules() -> list[Path]:
    return [p for p in PKG.rglob("*.py") if p.relative_to(PKG).as_posix() not in ROOT_FILES]


def _top(path: Path) -> str:
    first = path.relative_to(PKG).parts[0]
    return first.removesuffix(".py")


def _imported_layers(path: Path) -> tuple[set[str], list[str]]:
    layers: set[str] = set()
    problems: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append(f"relative import at line {node.lineno}")
            elif node.module == "simulacrum":
                problems.append(f"'from simulacrum import ...' at line {node.lineno} (import the submodule)")
            elif node.module and node.module.startswith("simulacrum."):
                layers.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            layers.update(a.name.split(".")[1] for a in node.names if a.name.startswith("simulacrum."))
    return layers, problems


def test_every_top_level_module_is_assigned_to_a_layer() -> None:
    assert {_top(p) for p in _modules()} <= set(ALLOWED)


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.relative_to(PKG).as_posix())
def test_module_respects_dependency_rule(path: Path) -> None:
    layer = _top(path)
    layers, problems = _imported_layers(path)
    illegal = layers - ALLOWED[layer] - {layer}
    assert not problems, problems
    assert not illegal, f"{path.relative_to(PKG)} ({layer}) must not import {sorted(illegal)}"
