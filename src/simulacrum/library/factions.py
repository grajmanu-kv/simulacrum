"""Faction tier: LLM-driven intent, code-driven consequences.

The brain only chooses a *stance*; the actions below resolve it against the real world state.
"""

from __future__ import annotations

import math
import random
from typing import Any

from simulacrum.core.registry import actions, brains
from simulacrum.core.world import Agent, World
from simulacrum.library.actions import act_move
from simulacrum.library.movement import move_toward
from simulacrum.llm.base import LLMRequest, parse_json_object

STANCES = ("forage", "hunt", "trade", "raid", "migrate", "found", "rest")
_SYL = ["ka", "ro", "mi", "ta", "vel", "dun", "sha", "or", "li", "ne", "bar", "zu", "ith", "ola"]
COUNCIL_SYSTEM = (
    "You are the ruling council of a small tribe in a simulated world. Choose ONE stance for the coming days. "
    'Reply with JSON only: {"stance": "forage|hunt|trade|raid|migrate|found|rest", '
    '"target": <neighbor id or null>, "say": "<one short in-world sentence>"}.'
)


def _make_name(rng: random.Random) -> str:
    return "".join(rng.choice(_SYL) for _ in range(rng.randint(2, 3))).capitalize()


def _remember(world: World, a: Agent, text: str) -> None:
    mem = a.attrs.setdefault("memory", [])
    mem.append(f"t{world.tick}: {text}")
    del mem[:-5]


def _prey_types(world: World, a: Agent) -> list[str]:
    return [r.target for r in world.rel_from.get(a.type, ()) if r.kind == "eats" and r.target in world.types]


def _decide(world: World, a: Agent, rng: random.Random, radius: float, field: str) -> None:
    nbrs = [
        {
            "id": b.id,
            "name": world.name_of(b),
            "pop": b.attrs.get("pop", 0),
            "food": round(b.attrs.get("food", 0), 1),
            "dist": round(d, 1),
            "affinity": world.affinity.get((a.id, b.id), 0.0),
        }
        for d, b in world.nearby(a, radius, [a.type])[:5]
    ]
    prey = _prey_types(world, a)
    ctx = {
        "kind": "decision",
        "id": a.id,
        "name": world.name_of(a),
        "trait": a.attrs.get("trait", "peaceful"),
        "pop": a.attrs.get("pop", 1),
        "food": round(a.attrs.get("food", 0), 1),
        "stance": a.attrs.get("stance"),
        "season": world.globals.get("season"),
        "radius": radius,
        "local_plants": round(world.field_mean(field, a.x, a.y, 3), 2),
        "local_prey": len(world.nearby(a, 3.5, prey)) if prey else 0,
        "neighbors": nbrs,
        "memory": a.attrs.get("memory", [])[-4:],
    }
    prompt = (
        f"You are {ctx['name']} (temperament: {ctx['trait']}). Population {ctx['pop']}, food stock {ctx['food']}, "
        f"current stance {ctx['stance']}. Season: {ctx['season']}. Local plant density {ctx['local_plants']}, "
        f"game nearby {ctx['local_prey']}. Neighbours (affinity -1 hostile .. +1 friendly): {nbrs}. "
        f"Recent history: {ctx['memory']}. Choose your stance."
    )
    text = world.llm.complete(LLMRequest(world.tick, f"{a.id}:decide", COUNCIL_SYSTEM, prompt, ctx))
    obj = parse_json_object(text) or {}
    stance = obj.get("stance") if obj.get("stance") in STANCES else "forage"
    target = obj.get("target") if isinstance(obj.get("target"), int) else None
    a.attrs["stance"], a.attrs["target"] = stance, target if target is not None else -1
    say = str(obj.get("say", ""))[:140]
    if say:
        world.emit("say", f"{world.name_of(a)}: {say}", throttle_key=("say", a.id), every=15)


@brains.register("faction")
def faction(
    world: World, a: Agent, rng: random.Random, think_every: int = 6, radius: float = 10, field: str = "plants"
) -> dict[str, Any]:
    at = a.attrs
    if "name" not in at:
        at["name"] = _make_name(rng)
        at.setdefault("pop", 10)
        at.setdefault("food", 15.0)
    if "stance" not in at or (world.tick + a.id) % think_every == 0:
        _decide(world, a, rng, radius, field)
    return {"op": at.get("stance", "forage"), "target": at.get("target", -1)}


def _resolve_target(world: World, a: Agent, act: dict, radius: float) -> Agent | None:
    b = world.agents.get(act.get("target", -1))
    if b is not None and b.alive and b.id != a.id and b.type == a.type and math.hypot(b.x - a.x, b.y - a.y) <= radius:
        return b
    near = world.nearby(a, radius, [a.type])
    return near[0][1] if near else None


@actions.register("forage")
def act_forage(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    name = act.get("field", "plants")
    arr = world.fields[name]
    pop = a.attrs.get("pop", 1)
    if a.attrs.get("food", 0.0) >= pop * 8:  # granaries full: no need to strip the land
        return
    budget, got = pop * 0.20, 0.0
    for cx, cy in world.cells_within(a.x, a.y, 3):
        if budget - got <= 1e-9:
            break
        i = world.idx(cx, cy)
        take = min(arr[i] * 0.35, budget - got)
        if take > 0:
            arr[i] -= take
            got += take
    a.attrs["food"] = round(a.attrs.get("food", 0.0) + got, 3)


@actions.register("hunt")
def act_hunt(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    kills, cap = 0, max(1, a.attrs.get("pop", 1) // 15)
    for _, p in world.nearby(a, 3.5, _prey_types(world, a)):
        if kills >= cap:
            break
        if rng.random() < 0.45:
            body = p.energy + 0.5 * world.types[p.type].max_energy
            a.attrs["food"] = round(
                a.attrs.get("food", 0.0) + world.rel_param(a.type, "eats", p.type, "gain", 0.5) * body, 3
            )
            world.kill(p, "hunted")
            world.bump("hunted")
            kills += 1


@actions.register("trade")
def act_trade(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    b = _resolve_target(world, a, act, 10)
    if b is None:
        return act_forage(world, a, act, rng)
    bonus = 0.12 * min(a.attrs.get("pop", 1), b.attrs.get("pop", 1))  # gains from trade
    a.attrs["food"] += bonus
    b.attrs["food"] += bonus
    flow = (a.attrs["food"] - b.attrs["food"]) * 0.10
    a.attrs["food"] = round(a.attrs["food"] - flow, 3)
    b.attrs["food"] = round(b.attrs["food"] + flow, 3)
    world.shift_affinity(a.id, b.id, 0.06)
    world.shift_affinity(b.id, a.id, 0.06)
    world.emit(
        "trade",
        f"{world.name_of(a)} trades with {world.name_of(b)}",
        throttle_key=("trade", min(a.id, b.id), max(a.id, b.id)),
        every=14,
    )


@actions.register("raid")
def act_raid(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    b = _resolve_target(world, a, act, 10)
    if b is None:
        return act_forage(world, a, act, rng)
    steal = min(b.attrs.get("food", 0.0) * 0.30, a.attrs.get("pop", 1) * 1.5)
    a.attrs["food"] = round(a.attrs["food"] + steal * 0.85, 3)
    b.attrs["food"] = round(b.attrs["food"] - steal, 3)
    if rng.random() < 0.25 and b.attrs.get("pop", 1) > 1:
        b.attrs["pop"] -= 1
    if rng.random() < 0.10 and a.attrs.get("pop", 1) > 1:
        a.attrs["pop"] -= 1
    world.shift_affinity(b.id, a.id, -0.35)
    world.shift_affinity(a.id, b.id, -0.10)
    _remember(world, a, f"raided {world.name_of(b)}")
    _remember(world, b, f"was raided by {world.name_of(a)}")
    world.bump("raids")
    world.emit(
        "raid",
        f"{world.name_of(a)} raids {world.name_of(b)} (+{steal * 0.85:.1f} food)",
        level="major",
        throttle_key=("raid", a.id, b.id),
        every=8,
    )


@actions.register("migrate")
def act_migrate(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    if rng.random() < 0.5:
        return
    arr = world.fields[act.get("field", "plants")]
    best, best_v = None, -1.0
    for cx, cy in world.cells_within(a.x, a.y, 8):
        if not world.can_enter(a, cx, cy):
            continue
        v = arr[world.idx(cx, cy)] - 0.02 * math.hypot(cx - a.x, cy - a.y)
        if v > best_v:
            best, best_v = (cx, cy), v
    if best and best != (a.x, a.y):
        step = move_toward(world, a, rng, *best)
        if step:
            act_move(world, a, step, rng)


@actions.register("found")
def act_found(world: World, a: Agent, act: dict, rng: random.Random) -> None:
    pop, food = a.attrs.get("pop", 1), a.attrs.get("food", 0.0)
    if pop < 12 or food < 20:
        return act_forage(world, a, act, rng)
    cells = [(cx, cy) for cx, cy in world.cells_within(a.x, a.y, 4) if world.can_enter(a, cx, cy)]
    if not cells:
        return
    x, y = rng.choice(cells)
    child_pop = pop // 2
    child = world.spawn(a.type, x, y, attrs={"pop": child_pop, "food": round(food / 2, 3), "name": _make_name(rng)})
    if child is None:
        return
    a.attrs["pop"], a.attrs["food"] = pop - child_pop, round(food / 2, 3)
    world.shift_affinity(a.id, child.id, 0.5)
    world.shift_affinity(child.id, a.id, 0.5)
    world.bump("settlements_founded")
    world.emit("faction", f"{world.name_of(a)} founds {world.name_of(child)}", level="major")
