from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from simulacrum.core.registry import brains
from simulacrum.engine import discover_entry_point_plugins, load_plugins
from simulacrum.errors import PluginLoadError, PluginSecurityError


def test_file_plugin_must_live_under_root(tmp_path: Path, eco_dir: Path) -> None:
    evil = tmp_path / "evil.py"
    evil.write_text("raise SystemExit('should never import')")
    with pytest.raises(PluginSecurityError):
        load_plugins([str(evil)], tmp_path, root=eco_dir)


def test_dotdot_escape_is_refused(eco_dir: Path) -> None:
    with pytest.raises(PluginSecurityError):
        load_plugins(["../../../../etc/hosts.py"], eco_dir, root=eco_dir)


def test_missing_plugin_file_and_module_raise_load_error(tmp_path: Path) -> None:
    with pytest.raises(PluginLoadError, match="not found"):
        load_plugins(["nope.py"], tmp_path, root=tmp_path)
    with pytest.raises(PluginLoadError):
        load_plugins(["definitely_not_a_module_xyz"], None)


def test_file_plugin_registers_components(tmp_path: Path) -> None:
    (tmp_path / "p.py").write_text(
        "from simulacrum.core.registry import brains\n"
        "@brains.register('file_plugin_brain')\n"
        "def b(world, a, rng):\n    return None\n"
    )
    load_plugins(["p.py"], tmp_path, root=tmp_path)
    assert "file_plugin_brain" in brains


class _EP:
    def __init__(self, name: str, fn: Any) -> None:
        self.name, self._fn = name, fn

    def load(self) -> Any:
        return self._fn()


def test_entry_point_plugins_load_and_a_broken_one_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    def good() -> None:
        brains.register("entry_point_brain")(lambda world, a, rng: None)

    def broken() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "simulacrum.engine.plugins.metadata.entry_points", lambda group: [_EP("broken", broken), _EP("good", good)]
    )
    assert discover_entry_point_plugins() == ["good"]
    assert "entry_point_brain" in brains
