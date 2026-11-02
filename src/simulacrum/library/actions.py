"""Built-in generic actions. Brains return action dicts; the engine dispatches them here."""

from __future__ import annotations

import random

from simulacrum.core.registry import actions
from simulacrum.core.world import Agent, World


@actions.register("move")
def act_move(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    nx, ny = a.x + act["dx"], a.y + act["dy"]
    if not world.can_enter(a, nx, ny):
        return
    cost = world.terrain_spec(nx, ny).move_cost * world.effect_mult("move_cost", nx, ny)
    if cost > 1 and rng.random() > 1 / cost:
        return
    world.move_agent(a, nx, ny)


@actions.register("rest")
def act_rest(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    return None


@actions.register("eat_field")
def act_eat_field(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    name, rate = act.get("field", "plants"), act.get("rate", 0.5)
    arr, i = world.fields[name], world.idx(a.x, a.y)
    amt = min(arr[i], rate)
    if amt <= 0:
        return
    gain = world.rel_param(a.type, "eats", f"field:{name}", "gain", 1.0)
    arr[i] -= amt
    a.energy = min(world.types[a.type].max_energy, a.energy + amt * gain)


@actions.register("attack")
def act_attack(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    tgt = world.agents.get(act["target"])
    if tgt is None or not tgt.alive or (tgt.x - a.x) ** 2 + (tgt.y - a.y) ** 2 > 2:
        return
    p = world.rel_param(a.type, "eats", tgt.type, "success", 0.6)
    p *= world.rel_param(a.type, "eats", tgt.type, "refuge", {}).get(world.terrain_at(tgt.x, tgt.y), 1.0)
    if rng.random() < p:
        body = tgt.energy + 0.5 * world.types[tgt.type].max_energy
        a.energy = min(
            world.types[a.type].max_energy, a.energy + world.rel_param(a.type, "eats", tgt.type, "gain", 0.6) * body
        )
        world.kill(tgt, "predation")
        world.bump("predation")
