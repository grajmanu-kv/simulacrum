"""The Garden: two people and a god.

* ``person``  brain: eat, keep company, share when well fed, and (if proud and starving) take from the other.
* ``deity``   brain: every few ticks, looks at the two people and chooses a miracle: bless, trial, mercy or
  silence. The choice goes through the LLM provider, so it is recorded and replayable; offline, a small
  heuristic answers (``register_stub_responder``). The god acts only through the same effects and energy
  changes a user perturbation would, never by editing agents' decisions.
* ``give`` / ``snatch`` actions and a ``manna`` perturbation (you, as a second god, feed someone).

The offline god's temperament is a rule, not a discovery: it rewards kindness and tests comfort. Swap in a
model (``llm: "anthropic"``) to let the choice come from somewhere else.
"""

from __future__ import annotations

import random
from typing import Any

from simulacrum.core.registry import actions, brains, perturbation
from simulacrum.core.world import Agent, World
from simulacrum.llm import LLMRequest, parse_json_object, register_stub_responder

NAMES = ["Ila", "Oren"]
# Ila is the better forager, Oren the weaker one: an imbalance is what gives sharing and quarrelling a reason to exist.
BITE = {"Ila": 0.8, "Oren": 0.4}
MIRACLES = ("bless", "trial", "mercy", "silence")
SYSTEM = (
    "You are the only god of a small garden world with two people. Each season you may bless them, put them "
    "to a trial, show mercy, or stay silent. Reply with JSON only: "
    '{"act": "bless|trial|mercy|silence", "target": <person id>, "say": "<one short sentence, or empty>"}.'
)


def _near(a: Agent, b: Agent) -> bool:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 <= 2


# ----------------------------------------------------------------------------- people
@brains.register("person")
def person(
    world: World,
    a: Agent,
    rng: random.Random,
    vision: float = 6,
    eat_below: float = 0.85,
    give_above: float = 0.7,
    desperate: float = 0.2,
    field: str = "plants",
) -> dict[str, Any] | None:
    a.attrs.setdefault("name", NAMES[a.id % len(NAMES)])
    cap = world.types[a.type].max_energy
    frac = a.energy / cap
    others = world.nearby(a, vision, ["person"])
    other = others[0][1] if others else None

    if other is not None and _near(a, other):
        if frac > give_above and other.energy / cap < 0.5:
            return {"op": "give", "target": other.id}
        if frac < desperate and other.energy > a.energy * 1.5 and a.attrs.get("temper") == "proud":
            return {"op": "snatch", "target": other.id}

    if frac < eat_below:
        if world.field_at(field, a.x, a.y) >= 0.08:
            return {"op": "eat_field", "field": field, "rate": BITE.get(a.attrs["name"], 0.5)}
        best, best_v = None, 0.0
        for cx, cy in world.cells_within(a.x, a.y, vision):
            if not world.can_enter(a, cx, cy):
                continue
            v = world.field_at(field, cx, cy) / (1 + 0.35 * ((cx - a.x) ** 2 + (cy - a.y) ** 2) ** 0.5)
            if v > best_v:
                best, best_v = (cx, cy), v
        if a.attrs.get("temper") == "gentle" and other is not None and other.energy / cap > give_above:
            return _step_toward(world, a, rng, other.x, other.y)  # the gentle ask for help; the proud do not
        if best is not None and best_v > 0.06 and best != (a.x, a.y):
            return _step_toward(world, a, rng, *best)
    elif other is not None and not _near(a, other):
        return _step_toward(world, a, rng, other.x, other.y)  # fed: seek company
    return _step_toward(world, a, rng, a.x + rng.choice((-1, 0, 1)), a.y + rng.choice((-1, 0, 1)))


def _step_toward(world: World, a: Agent, rng: random.Random, tx: int, ty: int) -> dict[str, Any] | None:
    options = [
        (dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and world.can_enter(a, a.x + dx, a.y + dy)
    ]
    if not options:
        return None
    rng.shuffle(options)
    dx, dy = min(options, key=lambda d: (a.x + d[0] - tx) ** 2 + (a.y + d[1] - ty) ** 2)
    return {"op": "move", "dx": dx, "dy": dy}


@actions.register("give")
def act_give(world: World, a: Agent, act: dict[str, Any], rng: random.Random) -> None:
    b = world.agents.get(act["target"])
    if b is None or not b.alive or not _near(a, b):
        return
    cap = world.types[a.type].max_energy
    amount = min(3.0, max(0.0, a.energy - 0.5 * cap), cap - b.energy)
    if amount <= 0:
        return
    a.energy -= amount
    b.energy += amount
    world.shift_affinity(a.id, b.id, 0.08)
    world.shift_affinity(b.id, a.id, 0.12)
    world.bump("gifts")
    world.emit(
        "kindness", f"{world.name_of(a)} shares food with {world.name_of(b)}", throttle_key=("give", a.id), every=12
    )


@actions.register("snatch")
def act_snatch(world: World, a: Agent, act: dict[str, Any], rng: random.Random) -> None:
    b = world.agents.get(act["target"])
    if b is None or not b.alive or not _near(a, b):
        return
    cap = world.types[a.type].max_energy
    amount = min(3.0, b.energy * 0.4, cap - a.energy)
    if amount <= 0:
        return
    b.energy -= amount
    a.energy += amount
    world.shift_affinity(b.id, a.id, -0.4)
    world.shift_affinity(a.id, b.id, -0.1)
    world.bump("snatches")
    world.emit(
        "quarrel",
        f"{world.name_of(a)} takes food from {world.name_of(b)}",
        level="major",
        throttle_key=("snatch", a.id),
        every=12,
    )


# ----------------------------------------------------------------------------- the god
@register_stub_responder("deity")
def offline_god(ctx: dict[str, Any], u: float) -> dict[str, Any]:
    """Offline stand-in for the god's choice: reward kindness, test comfort, rescue the starving."""
    people = ctx["people"]
    weakest = min(people, key=lambda p: (p["energy"], p["id"]))
    thriving = all(p["energy"] > 0.65 for p in people)
    bond = ctx["bond"]
    if weakest["energy"] < 0.2 and u < 0.85:
        return {"act": "mercy", "target": weakest["id"], "say": f"Rise, {weakest['name']}. You are not forgotten."}
    if thriving and bond < -0.1 and u < 0.6:
        return {"act": "trial", "target": people[0]["id"], "say": "Plenty has hardened you. Learn from want."}
    if bond > 0.15 and weakest["energy"] > 0.3 and u < 0.55:
        return {"act": "bless", "target": weakest["id"], "say": "Kindness is its own harvest."}
    if thriving and u < 0.25:
        return {"act": "trial", "target": people[-1]["id"], "say": "Comfort, too, is a test."}
    return {"act": "silence", "target": weakest["id"], "say": ""}


@brains.register("deity")
def deity(
    world: World,
    a: Agent,
    rng: random.Random,
    think_every: int = 8,
    duration: int = 20,
    bless_radius: float = 6,
    trial_radius: float = 8,
) -> None:
    if (world.tick + a.id) % think_every:
        return None
    people = sorted((p for p in world.alive_agents() if p.type == "person"), key=lambda p: p.id)
    if not people:
        world.emit("god", "The garden is empty. The god waits.", throttle_key="empty", every=50)
        return None
    cap = world.types[people[0].type].max_energy
    bond = 0.0
    if len(people) == 2:
        p, q = people
        bond = (world.affinity.get((p.id, q.id), 0.0) + world.affinity.get((q.id, p.id), 0.0)) / 2
    ctx = {
        "kind": "deity",
        "tick": world.tick,
        "season": world.globals.get("season"),
        "rain": world.globals.get("rain"),
        "bond": round(bond, 3),
        "people": [
            {"id": p.id, "name": world.name_of(p), "energy": round(p.energy / cap, 2), "temper": p.attrs.get("temper")}
            for p in people
        ],
        "recent": a.attrs.get("memory", [])[-3:],
    }
    prompt = f"State of the garden: {ctx}. Choose."
    reply = parse_json_object(world.llm.complete(LLMRequest(world.tick, f"{a.id}:deity", SYSTEM, prompt, ctx))) or {}
    act = reply.get("act") if reply.get("act") in MIRACLES else "silence"
    ids = {p.id: p for p in people}
    raw_target = reply.get("target")
    target = ids.get(raw_target) if isinstance(raw_target, int) else None
    target = target or min(people, key=lambda p: (p.energy, p.id))
    say = str(reply.get("say", ""))[:140]

    if act == "bless":
        world.add_effect("growth", duration, 1.8, x=target.x, y=target.y, radius=bless_radius, label="blessing")
        world.emit("god", f"A blessing rests on {world.name_of(target)}", level="major")
    elif act == "trial":
        world.add_effect("growth", duration, 0.35, x=target.x, y=target.y, radius=trial_radius, label="trial")
        world.emit("god", f"A trial is set before {world.name_of(target)}", level="major")
    elif act == "mercy":
        target.energy = min(cap, target.energy + 0.5 * cap)
        world.emit("god", f"Mercy is shown to {world.name_of(target)}", level="major")
    if act != "silence":
        world.bump(f"miracles:{act}")
        mem = a.attrs.setdefault("memory", [])
        mem.append(f"t{world.tick}: {act} -> {world.name_of(target)}")
        del mem[:-5]
    if say:
        world.emit("god", f"God: {say}", level="story")
    return None


# ----------------------------------------------------------------------------- you, as a second god
@perturbation(
    "manna",
    label="Send manna (feed someone)",
    description="Restores energy to the person nearest the chosen cell.",
    params={
        "x": {"type": "int", "default": 15, "role": "x", "label": "X (click map)"},
        "y": {"type": "int", "default": 10, "role": "y", "label": "Y (click map)"},
        "amount": {"type": "float", "default": 12.0, "min": 1.0, "max": 30.0, "label": "Energy"},
    },
)
def manna(world: World, rng: random.Random, x: int, y: int, amount: float) -> str:
    people = [p for p in world.alive_agents() if p.type == "person"]
    if not people:
        return "Manna falls on an empty garden"
    p = min(people, key=lambda q: ((q.x - x) ** 2 + (q.y - y) ** 2, q.id))
    p.energy = min(world.types[p.type].max_energy, p.energy + amount)
    return f"Manna falls near {world.name_of(p)} (+{amount:g} energy)"