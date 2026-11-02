from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path

from simulacrum import Engine


def test_same_seed_same_world_different_seed_differs(forest: Callable[..., Engine]) -> None:
    a, b, c = forest(5), forest(5), forest(6)
    for e in (a, b, c):
        e.run(80)
    assert a.world.state_hash() == b.world.state_hash()
    assert a.world.state_hash() != c.world.state_hash()


def test_replay_reproduces_run_with_perturbations(forest: Callable[..., Engine], eco_dir: Path) -> None:
    e = forest(7)
    e.run(30)
    e.perturb("drought", {"x": 20, "y": 15, "radius": 8, "duration": 20, "intensity": 0.8})
    e.perturb("plague", {"type": "grazer", "fraction": 0.3})
    e.run(60)
    log = json.loads(json.dumps(e.export_log()))  # survives a JSON round trip, as the API does
    assert log["perturbations"] and log["llm"]
    assert Engine.verify(log, base_dir=eco_dir)["ok"]


def test_replay_detects_tampering(forest: Callable[..., Engine], eco_dir: Path) -> None:
    e = forest(7)
    e.run(20)
    e.perturb("plague", {"type": "grazer", "fraction": 0.5})
    e.run(20)
    log = e.export_log()
    bad = copy.deepcopy(log)
    bad["perturbations"][0]["params"]["fraction"] = 0.1
    assert not Engine.verify(bad, base_dir=eco_dir)["ok"]
    bad2 = copy.deepcopy(log)
    bad2["final_hash"] = "0" * 16
    assert not Engine.verify(bad2, base_dir=eco_dir)["ok"]


def test_replay_serves_recorded_llm_responses_not_a_provider(forest: Callable[..., Engine], eco_dir: Path) -> None:
    e = forest(7)
    e.run(40)
    log = e.export_log()
    log["llm"] = [dict(r, response='{"stance": "rest"}') for r in log["llm"]]  # different "model" output
    assert not Engine.verify(log, base_dir=eco_dir)["ok"]


def test_replay_reports_divergence_when_a_response_was_never_recorded(
    forest: Callable[..., Engine], eco_dir: Path
) -> None:
    e = forest(7)
    e.run(40)
    log = e.export_log()
    log["llm"] = []
    result = Engine.verify(log, base_dir=eco_dir)
    assert result["ok"] is False and "no recorded LLM response" in result["error"]
