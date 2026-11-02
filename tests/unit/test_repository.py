from __future__ import annotations

from pathlib import Path

import pytest

from simulacrum.errors import EcosystemNotFound
from simulacrum.repository import EcosystemRepository


def test_lists_bundled_ecosystems(eco_dir: Path) -> None:
    ids = {e["id"] for e in EcosystemRepository(eco_dir).list()}
    assert {"forest", "junction"} <= ids


def test_load_returns_spec_and_plugin_base_dir(eco_dir: Path) -> None:
    spec, base = EcosystemRepository(eco_dir).load("junction")
    assert spec.plugins == ["junction_plugin.py"] and base == eco_dir


@pytest.mark.parametrize("bad", ["../../etc/passwd", "..", "ghost", "forest/../../x"])
def test_unknown_or_escaping_ids_are_not_found(eco_dir: Path, bad: str) -> None:
    with pytest.raises(EcosystemNotFound):
        EcosystemRepository(eco_dir).load(bad)


def test_unreadable_files_are_skipped_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{nope")
    (tmp_path / "ok.json").write_text('{"name": "Ok"}')
    assert [e["id"] for e in EcosystemRepository(tmp_path).list()] == ["ok"]
