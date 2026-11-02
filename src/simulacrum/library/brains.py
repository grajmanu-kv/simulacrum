"""Built-in rule brains (the cheap tier that drives most agents)."""

from __future__ import annotations

import math
import random
from typing import Any

from simulacrum.core.registry import brains
from simulacrum.core.world import Agent, World
from simulacrum.library.movement import move_by_score, move_toward


@brains.register("wander")
def wander(world: World, a: Agent, rng: random.Random, **_: Any) -> dict[str, Any] | None:
    return move_by_score(world, a, rng, lambda x, y: rng.random())


@brains.register("grazer")
def grazer(
    world: World,
    a: Agent,
    rng: random.Random,
    vision: float = 3,
    field: str = "plants",
    bite: float = 0.5,
    eat_below: float = 0.9,
) -> dict[str, Any] | None:
    t = world.types[a.type]
    predators = [r.source for r in world.rel_to.get(a.type, ()) if r.kind == "eats" and r.source in world.types]
    if predators:
        near = world.nearby(a, vision, predators)
        if near:
            p = near[0][1]
            act = move_by_score(world, a, rng, lambda x, y: (x - p.x) ** 2 + (y - p.y) ** 2)
            if act:
                return act
    if a.energy < t.max_energy * eat_below and world.field_at(field, a.x, a.y) >= 0.08:
        return {"op": "eat_field", "field": field, "rate": bite}
    best, best_v = None, 0.0
    arr = world.fields[field]
    for cx, cy in world.cells_within(a.x, a.y, vision):
        v = arr[world.idx(cx, cy)] / (1 + 0.35 * math.hypot(cx - a.x, cy - a.y))
        if v > best_v:
            best, best_v = (cx, cy), v
    if best and best_v > 0.06 and best != (a.x, a.y):
        return move_toward(world, a, rng, *best)
    return move_by_score(world, a, rng, lambda x, y: rng.random())


@brains.register("hunter")
def hunter(
    world: World, a: Agent, rng: random.Random, vision: float = 6, rest_above: float = 0.8
) -> dict[str, Any] | None:
    t = world.types[a.type]
    prey = [r.target for r in world.rel_from.get(a.type, ()) if r.kind == "eats" and r.target in world.types]
    if a.energy > t.max_energy * rest_above:
        return move_by_score(world, a, rng, lambda x, y: rng.random())
    near = world.nearby(a, vision, prey)
    if not near:
        return move_by_score(world, a, rng, lambda x, y: rng.random())
    d, p = near[0]
    if d <= 1.5:
        return {"op": "attack", "target": p.id}
    return move_toward(world, a, rng, p.x, p.y)
