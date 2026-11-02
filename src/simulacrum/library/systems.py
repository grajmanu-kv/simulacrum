"""Built-in systems: aggregate per-tick rules (growth, metabolism, reproduction, economy)."""

from __future__ import annotations

import random

from simulacrum.core.registry import systems
from simulacrum.core.world import World
from simulacrum.library.movement import DIRS8


@systems.register("plant_growth")
def plant_growth(
    world: World, rng: random.Random, field: str = "plants", rate: float = 0.12, seed: float = 0.01, relax: float = 0.05
) -> None:
    """Logistic regrowth toward a per-cell carrying capacity (terrain capacity x environment x effects)."""
    arr = world.fields[field]
    fmax = next(f.max for f in world.spec.environment.fields if f.name == field)
    g_env = world.globals.get("season_growth", 1.0) * (0.6 + 0.8 * world.globals.get("rain", 0.5))
    terr = world.spec.environment.terrains
    has_fx = bool(world.effects)
    w = world.w
    for y in range(world.h):
        for x in range(w):
            i = y * w + x
            cap = terr[world.terrain[i]].capacity
            p = arr[i]
            if cap <= 0:
                arr[i] = p * 0.9
                continue
            g = g_env * (world.effect_mult("growth", x, y) if has_fx else 1.0)
            capg = cap * min(1.0, g)
            if capg <= 1e-6:
                arr[i] = p * 0.95
            elif p > capg:
                arr[i] = p - relax * (p - capg)
            else:
                arr[i] = min(fmax, max(0.0, p + rate * g * (p + seed * cap) * (1 - p / capg)))


@systems.register("metabolism")
def metabolism(world: World, rng: random.Random) -> None:
    for a in list(world.agents.values()):
        if not a.alive:
            continue
        t = world.types[a.type]
        a.energy -= t.metabolism
        if a.energy <= 0 and t.metabolism > 0:
            world.kill(a, "starvation")
        elif t.lifespan and a.age >= t.lifespan:
            world.kill(a, "old_age")


@systems.register("reproduction")
def reproduction(world: World, rng: random.Random) -> None:
    for a in list(world.agents.values()):
        if not a.alive:
            continue
        r = world.types[a.type].reproduce
        if r is None or a.energy < r.threshold or a.age < r.min_age:
            continue
        if rng.random() > r.chance:
            continue
        if len(world.nearby(a, r.radius, [a.type])) >= r.max_local:
            continue
        cells = [(a.x + dx, a.y + dy) for dx, dy in DIRS8 if world.can_enter_type(a.type, a.x + dx, a.y + dy)]
        if not cells:
            continue
        x, y = rng.choice(cells)
        if world.spawn(a.type, x, y, energy=r.offspring_energy):
            a.energy -= r.cost
            world.bump(f"births:{a.type}")


@systems.register("affinity_decay")
def affinity_decay(world: World, rng: random.Random, rate: float = 0.02) -> None:
    for key in list(world.affinity):
        a, b = key
        if a not in world.agents or b not in world.agents:
            del world.affinity[key]
            continue
        v = world.affinity[key] * (1 - rate)
        if abs(v) < 0.01:
            del world.affinity[key]
        else:
            world.affinity[key] = round(v, 4)


@systems.register("faction_economy")
def faction_economy(
    world: World,
    rng: random.Random,
    types: list[str] | None = None,
    consumption: float = 0.08,
    growth_chance: float = 0.05,
    growth_food: float = 2.0,
    max_pop: int = 60,
) -> None:
    types = types or ["tribe"]
    for a in list(world.agents.values()):
        if not a.alive or a.type not in types:
            continue
        pop, food = a.attrs.get("pop", 1), a.attrs.get("food", 0.0)
        need = pop * consumption
        if food >= need:
            food -= need
            if food > pop * growth_food and pop < max_pop and rng.random() < growth_chance:
                pop += 1
        else:
            food = 0.0
            if rng.random() < 0.5:
                pop -= 1
        a.attrs["pop"], a.attrs["food"] = pop, round(food, 3)
        if pop <= 0:
            world.kill(a, "collapse")
            world.emit("faction", f"{world.name_of(a)} has collapsed", level="major")
