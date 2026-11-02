"""Built-in environment agents: things that change the world without being part of it."""

from __future__ import annotations

import math
import random

from simulacrum.core.registry import env_agents
from simulacrum.core.world import World


@env_agents.register("season")
def season(world: World, rng: random.Random, period: int = 160) -> None:
    phase = (world.tick % period) / period
    world.globals["season"] = ["spring", "summer", "autumn", "winter"][int(phase * 4) % 4]
    world.globals["season_growth"] = round(1.0 + 0.5 * math.sin(2 * math.pi * (phase - 0.125)), 3)


@env_agents.register("weather")
def weather(
    world: World, rng: random.Random, storm_chance: float = 0.008, rain_pull: float = 0.08, rain_noise: float = 0.06
) -> None:
    rain = world.globals.get("rain", 0.5)
    rain += (0.5 - rain) * rain_pull + rng.uniform(-rain_noise, rain_noise)
    world.globals["rain"] = round(max(0.0, min(1.0, rain)), 3)
    if rng.random() < storm_chance:
        x, y, r = rng.randrange(world.w), rng.randrange(world.h), rng.randint(4, 8)
        dur = rng.randint(5, 12)
        world.add_effect("move_cost", dur, 1.8, x=x, y=y, radius=r, label="storm")
        world.emit("weather", f"A storm breaks over ({x},{y})", throttle_key="storm", every=10)
