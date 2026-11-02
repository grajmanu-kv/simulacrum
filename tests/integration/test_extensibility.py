from __future__ import annotations

import random
from typing import Any

from simulacrum import EcosystemSpec, Engine, brains, perturbation, systems
from simulacrum.core.world import Agent, World


def test_user_defined_brain_system_and_perturbation() -> None:
    @brains.register("test_climber")
    def climber(world: World, a: Agent, rng: random.Random) -> dict[str, Any]:
        return {"op": "move", "dx": 1, "dy": 0}

    @systems.register("test_counter")
    def counter(world: World, rng: random.Random, per_tick: int = 2) -> None:
        world.bump("custom_ticks", per_tick)

    @perturbation("test_boom", params={"count": {"type": "int", "default": 3, "min": 1, "max": 10}})
    def boom(world: World, rng: random.Random, count: int) -> str:
        for _ in range(count):
            world.spawn("walker", 1, 1)
        return f"boom x{count}"

    spec = EcosystemSpec.model_validate(
        {
            "name": "toy",
            "seed": 1,
            "environment": {
                "width": 10,
                "height": 4,
                "terrains": {"flat": {}},
                "generator": {"kind": "noise_terrain", "params": {}},
            },
            "agent_types": [{"name": "walker", "brain": "test_climber", "initial": {"count": 1}}],
            "systems": [{"kind": "test_counter", "params": {"per_tick": 5}}],
            "perturbations": ["test_boom"],
        }
    )
    e = Engine(spec)
    e.perturb("test_boom", {"count": 4})
    e.run(3)
    assert e.world.counters["custom_ticks"] == 15
    assert e.world.count("walker") == 5
    assert Engine.verify(e.export_log())["ok"]
