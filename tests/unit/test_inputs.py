from __future__ import annotations

from collections.abc import Callable

import pytest

from simulacrum import Engine
from simulacrum.errors import PerturbationError


def test_catalog_resolves_symbolic_choices_and_map_bounds(forest: Callable[..., Engine]) -> None:
    e = forest(7)
    cat = {c["name"]: c for c in e.perturbation_catalog()}
    assert "water" in cat["terraform"]["params"]["terrain"]["choices"]
    assert "hunter" in cat["introduce"]["params"]["type"]["choices"]
    assert cat["drought"]["params"]["x"]["max"] == e.world.w - 1


def test_validation_rejects_unknown_disabled_or_bad_inputs(forest: Callable[..., Engine]) -> None:
    e = forest(7)
    with pytest.raises(PerturbationError, match="not enabled"):
        e.perturb("accident", {})  # exists only for the junction
    with pytest.raises(PerturbationError, match="unknown parameters"):
        e.perturb("drought", {"bogus": 1})
    with pytest.raises(PerturbationError):
        e.perturb("terraform", {"terrain": "lava"})


def test_values_are_clamped_not_trusted(forest: Callable[..., Engine]) -> None:
    e = forest(7)
    got = e.perturb("drought", {"intensity": 99, "x": 9999})
    assert got["params"]["intensity"] == 1.0 and got["params"]["x"] == e.world.w - 1


def test_replays_refuse_new_inputs(forest: Callable[..., Engine]) -> None:
    e = forest(7)
    e.run(3)
    replay = Engine(e.spec, replay=e.export_log())
    with pytest.raises(PerturbationError, match="replay"):
        replay.perturb("plague", {"type": "grazer"})
