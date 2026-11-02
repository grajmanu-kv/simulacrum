from __future__ import annotations

from collections.abc import Callable

from simulacrum import Engine


def test_junction_plugin_flows_and_fault_recovers(junction: Callable[..., Engine]) -> None:
    e = junction()
    e.run(150)
    assert e.world.counters.get("deaths:exited", 0) > 20
    e.perturb("signal_fault", {"mode": "all_green", "duration": 30})
    e.run(30)
    before = e.world.counters["deaths:exited"]
    e.run(80)
    assert e.world.counters["deaths:exited"] > before + 10  # keep-clear driving: no permanent gridlock


def test_junction_gridlock_when_keep_clear_disabled(junction: Callable[..., Engine]) -> None:
    e = junction(keep_clear=False)
    e.run(100)
    e.perturb("signal_fault", {"mode": "all_green", "duration": 30})
    e.run(60)
    before = e.world.counters["deaths:exited"]
    e.run(60)
    assert e.world.counters["deaths:exited"] == before  # circular wait inside the box


def test_accident_builds_queue(junction: Callable[..., Engine]) -> None:
    e = junction()
    e.run(60)
    base_wait = sum(r["metrics"]["avg_wait"] for r in e.history[-20:]) / 20
    e.perturb("accident", {"x": 14, "y": 12, "duration": 30})
    e.run(30)
    assert max(r["metrics"]["avg_wait"] for r in e.history[-30:]) > 2 * base_wait
