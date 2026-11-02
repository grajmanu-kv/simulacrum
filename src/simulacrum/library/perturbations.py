"""Built-in perturbations (external inputs). They change the environment, never an agent's prompt."""

from __future__ import annotations

import random

from simulacrum.core.registry import perturbation
from simulacrum.core.world import World

_X = {"type": "int", "default": 20, "role": "x", "label": "X (click map)"}
_Y = {"type": "int", "default": 15, "role": "y", "label": "Y (click map)"}


def _area(default_radius: int = 8) -> dict:
    return {
        "x": dict(_X),
        "y": dict(_Y),
        "radius": {
            "type": "int",
            "default": default_radius,
            "min": -1,
            "max": 60,
            "label": "Radius (-1 = whole world)",
        },
        "duration": {"type": "int", "default": 30, "min": 1, "max": 500, "label": "Duration (ticks)"},
    }


def _where(radius: int, x: int, y: int) -> str:
    return "worldwide" if radius < 0 else f"near ({x},{y})"


@perturbation(
    "drought",
    description="Lowers plant carrying capacity in an area for a while.",
    params={**_area(10), "intensity": {"type": "float", "default": 0.7, "min": 0.1, "max": 1.0, "label": "Intensity"}},
)
def p_drought(world: World, rng: random.Random, x: int, y: int, radius: int, duration: int, intensity: float) -> str:
    world.add_effect("growth", duration, max(0.0, 1 - intensity), x=x, y=y, radius=radius, label="drought")
    return f"Drought {_where(radius, x, y)} for {duration} ticks (growth x{1 - intensity:.2f})"


@perturbation(
    "heavy_rain",
    description="Boosts plant growth but slows movement.",
    params={
        **_area(12),
        "intensity": {"type": "float", "default": 0.6, "min": 0.1, "max": 2.0, "label": "Growth boost"},
    },
)
def p_rain(world: World, rng: random.Random, x: int, y: int, radius: int, duration: int, intensity: float) -> str:
    world.add_effect("growth", duration, 1 + intensity, x=x, y=y, radius=radius, label="heavy rain")
    world.add_effect("move_cost", duration, 1.4, x=x, y=y, radius=radius, label="heavy rain")
    return f"Heavy rain {_where(radius, x, y)} for {duration} ticks"


@perturbation("storm", description="Makes movement much harder and damages growth.", params=_area(8))
def p_storm(world: World, rng: random.Random, x: int, y: int, radius: int, duration: int) -> str:
    world.add_effect("move_cost", duration, 2.5, x=x, y=y, radius=radius, label="storm")
    world.add_effect("growth", duration, 0.85, x=x, y=y, radius=radius, label="storm")
    return f"Storm {_where(radius, x, y)} for {duration} ticks"


@perturbation(
    "flood",
    description="Blocks entry, washes out plants, and drowns some agents in the area.",
    params={
        "x": dict(_X),
        "y": dict(_Y),
        "radius": {"type": "int", "default": 5, "min": 1, "max": 30, "label": "Radius"},
        "duration": {"type": "int", "default": 25, "min": 1, "max": 300, "label": "Duration (ticks)"},
    },
)
def p_flood(world: World, rng: random.Random, x: int, y: int, radius: int, duration: int) -> str:
    world.add_effect("blocked", duration, 1.0, mode="add", x=x, y=y, radius=radius, label="flood")
    drowned = 0
    for cx, cy in world.cells_within(x, y, radius):
        for fname in world.fields:
            world.fields[fname][world.idx(cx, cy)] = 0.0
        for a in world.agents_at(cx, cy):
            if world.types[a.type].exclusive or rng.random() < 0.25:
                world.kill(a, "flood")
                drowned += 1
    return f"Flood at ({x},{y}) r={radius} for {duration} ticks; {drowned} agents lost"


@perturbation(
    "terraform",
    label="Change terrain (infrastructure)",
    description="Persistently rewrites terrain in a circle: build a road, dam a valley, clear a forest.",
    params={
        "x": dict(_X),
        "y": dict(_Y),
        "radius": {"type": "int", "default": 3, "min": 0, "max": 30, "label": "Radius"},
        "terrain": {"type": "choice", "choices": "@terrains", "label": "New terrain"},
    },
)
def p_terraform(world: World, rng: random.Random, x: int, y: int, radius: int, terrain: str) -> str:
    n = 0
    for cx, cy in world.cells_within(x, y, radius):
        world.terrain[world.idx(cx, cy)] = terrain
        n += 1
    return f"Terrain at ({x},{y}) r={radius} became {terrain} ({n} cells)"


@perturbation(
    "introduce",
    label="Introduce species",
    description="Drops new agents of an existing type into an area.",
    params={
        "type": {"type": "choice", "choices": "@agent_types", "label": "Agent type"},
        "x": dict(_X),
        "y": dict(_Y),
        "radius": {"type": "int", "default": 4, "min": 0, "max": 30, "label": "Radius"},
        "count": {"type": "int", "default": 10, "min": 1, "max": 100, "label": "Count"},
    },
)
def p_introduce(world: World, rng: random.Random, type: str, x: int, y: int, radius: int, count: int) -> str:
    cells = [c for c in world.cells_within(x, y, radius) if world.can_enter_type(type, *c)]
    placed = 0
    for _ in range(count):
        if not cells:
            break
        cx, cy = rng.choice(cells)
        if world.can_enter_type(type, cx, cy) and world.spawn(type, cx, cy):
            placed += 1
    return f"Introduced {placed} {type} near ({x},{y})"


@perturbation(
    "plague",
    description="Kills a fraction of one agent type everywhere.",
    params={
        "type": {"type": "choice", "choices": "@agent_types", "label": "Agent type"},
        "fraction": {"type": "float", "default": 0.4, "min": 0.05, "max": 1.0, "label": "Fraction killed"},
    },
)
def p_plague(world: World, rng: random.Random, type: str, fraction: float) -> str:
    n = 0
    for a in list(world.agents.values()):
        if a.alive and a.type == type and rng.random() < fraction:
            world.kill(a, "plague")
            n += 1
    return f"Plague strikes {type}: {n} died"
