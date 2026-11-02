"""Movement helpers shared by brains and actions."""

from __future__ import annotations

import random
from collections.abc import Callable

from simulacrum.core.world import Agent, World

DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def move_by_score(world: World, a: Agent, rng: random.Random, score: Callable[[int, int], float]) -> dict | None:
    dirs = DIRS8[:]
    rng.shuffle(dirs)
    best, best_s = None, -1e18
    for dx, dy in dirs:
        nx, ny = a.x + dx, a.y + dy
        if not world.can_enter(a, nx, ny):
            continue
        s = score(nx, ny)
        if s > best_s:
            best, best_s = (dx, dy), s
    return {"op": "move", "dx": best[0], "dy": best[1]} if best else None


def move_toward(world: World, a: Agent, rng: random.Random, tx: int, ty: int) -> dict | None:
    return move_by_score(world, a, rng, lambda x, y: -((x - tx) ** 2 + (y - ty) ** 2))
