"""Road-junction plugin.

Shows every extension point a third party can use: a world generator, an environment agent
(the signal controller), an agent brain, a system (spawner, stats) and typed perturbations.
Nothing here touches the engine; it only registers components by name.

Geometry: driving on the right. Eastbound uses the row below the centre line, westbound the row
above; southbound uses the left column of the vertical road, northbound the right one.
"""

from __future__ import annotations

import random
from typing import Any

from simulacrum.core.registry import brains, env_agents, generators, perturbation, systems
from simulacrum.core.world import Agent, World

DIRV = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
ARROW = {"E": ">", "W": "<", "S": "v", "N": "^"}


@generators.register("crossroads")
def crossroads(
    world: World, rng: random.Random, road: str = "road", box: str = "junction", ground: str = "grass"
) -> None:
    cx, cy = world.w // 2, world.h // 2
    for y in range(world.h):
        for x in range(world.w):
            on_h, on_v = cy - 1 <= y <= cy, cx - 1 <= x <= cx
            world.terrain[world.idx(x, y)] = box if on_h and on_v else road if on_h or on_v else ground
    world.globals["junction"] = {"cx": cx, "cy": cy}


@env_agents.register("signal")
def signal(world: World, rng: random.Random, green: int = 14, clearance: int = 2) -> None:
    """Fixed-time controller: NS green, all-red, EW green, all-red. Faults override it."""
    cycle = [("NS", green), ("ALL_RED", clearance), ("EW", green), ("ALL_RED", clearance)]
    s = world.globals.setdefault("signal", {"i": 0, "t": 0})
    s["t"] += 1
    if s["t"] > cycle[s["i"]][1]:
        s["i"], s["t"] = (s["i"] + 1) % len(cycle), 1
    phase = cycle[s["i"]][0]
    light = {"NS": phase == "NS", "EW": phase == "EW", "flash": 0.0}
    faults = world.effects_of("signal_fault")
    if faults:
        fault = faults[-1].data.get("fault", "all_red")
        if fault == "all_red":
            light = {"NS": False, "EW": False, "flash": 0.0}
        elif fault == "all_green":
            light = {"NS": True, "EW": True, "flash": 0.0}
        else:  # flashing: everybody may enter, but hesitates half the time
            light = {"NS": True, "EW": True, "flash": 0.5}
        phase = f"FAULT:{fault}"
    world.globals["light"] = light
    world.globals["signal_label"] = phase


def _path_clear(world: World, a: Agent, dx: int, dy: int) -> bool:
    """True if every junction cell ahead, plus the first cell beyond it, is free ("don't block the box")."""
    x, y = a.x + dx, a.y + dy
    while world.in_bounds(x, y) and world.terrain_at(x, y) == "junction":
        if not world.can_enter(a, x, y):
            return False
        x, y = x + dx, y + dy
    return not world.in_bounds(x, y) or world.can_enter(a, x, y)


@brains.register("drive")
def drive(world: World, a: Agent, rng: random.Random, keep_clear: bool = True) -> dict[str, Any] | None:
    """Straight-through driver. keep_clear=False lets cars enter the box regardless, which permits
    permanent gridlock when the signals fail (a circular wait inside the box)."""
    d = a.attrs["dir"]
    dx, dy = DIRV[d]
    nx, ny = a.x + dx, a.y + dy
    if not world.in_bounds(nx, ny):
        world.bump("trip_ticks", a.age)
        world.kill(a, "exited")
        return None
    light = world.globals.get("light", {})
    axis = "NS" if d in "NS" else "EW"
    entering = world.terrain_at(nx, ny) == "junction" and world.terrain_at(a.x, a.y) != "junction"
    if entering:
        if not light.get(axis, True) or (light.get("flash") and rng.random() < light["flash"]):
            a.attrs["wait"] += 1
            return None
        if keep_clear and not _path_clear(world, a, dx, dy):
            a.attrs["wait"] += 1
            return None
    speed = world.effect_mult("speed", a.x, a.y)
    if speed < 1 and rng.random() > speed:
        return None
    if not world.can_enter(a, nx, ny):
        a.attrs["wait"] += 1
        return None
    a.attrs["wait"] = 0
    return {"op": "move", "dx": dx, "dy": dy}


@systems.register("traffic_spawner")
def traffic_spawner(
    world: World, rng: random.Random, rate: float = 0.16, rates: dict[str, float] | None = None
) -> None:
    j = world.globals["junction"]
    cx, cy = j["cx"], j["cy"]
    entries = {"E": (0, cy), "W": (world.w - 1, cy - 1), "S": (cx - 1, 0), "N": (cx, world.h - 1)}
    surge = world.effect_mult("spawn_rate", 0, 0)
    for d, (x, y) in entries.items():
        r = (rates or {}).get(d, rate) * surge
        if rng.random() < r and world.can_enter_type("car", x, y):
            world.spawn("car", x, y, attrs={"dir": d, "wait": 0, "glyph": ARROW[d]})


@systems.register("traffic_stats")
def traffic_stats(world: World, rng: random.Random) -> None:
    cars = [a for a in world.agents.values() if a.alive]
    waiting = [a for a in cars if a.attrs.get("wait", 0) > 0]
    world.metrics["queue"] = len(waiting)
    world.metrics["avg_wait"] = sum(a.attrs["wait"] for a in cars) / len(cars) if cars else 0.0
    if len(waiting) >= 14:
        world.emit(
            "traffic", f"{len(waiting)} cars stopped at the junction", level="warn", throttle_key="queue", every=25
        )


# ----- perturbations -----------------------------------------------------------------
_X = {"type": "int", "default": 16, "role": "x", "label": "X (click map)"}
_Y = {"type": "int", "default": 12, "role": "y", "label": "Y (click map)"}
_DUR = {"type": "int", "default": 20, "min": 1, "max": 300, "label": "Duration (ticks)"}


@perturbation(
    "accident",
    description="Blocks one cell (click a road cell). Queues build behind it.",
    params={"x": _X, "y": _Y, "duration": _DUR},
)
def accident(world: World, rng: random.Random, x: int, y: int, duration: int) -> str:
    world.add_effect("blocked", duration, 1.0, mode="add", x=x, y=y, radius=0, label="accident")
    return f"Accident at ({x},{y}) blocks the road for {duration} ticks"


@perturbation(
    "signal_fault",
    description="Overrides the controller.",
    params={
        "mode": {"type": "choice", "choices": ["all_red", "all_green", "flashing"], "label": "Fault mode"},
        "duration": _DUR,
    },
)
def signal_fault(world: World, rng: random.Random, mode: str, duration: int) -> str:
    world.add_effect("signal_fault", duration, 1.0, mode="add", label=f"signal {mode}", fault=mode)
    return f"Signal fault ({mode}) for {duration} ticks"


@perturbation(
    "surge",
    description="Rush hour: multiplies arrival rates.",
    params={
        "factor": {"type": "float", "default": 2.5, "min": 1.0, "max": 6.0, "label": "Arrival multiplier"},
        "duration": _DUR,
    },
)
def surge(world: World, rng: random.Random, factor: float, duration: int) -> str:
    world.add_effect("spawn_rate", duration, factor, label="rush hour")
    return f"Rush hour x{factor:.1f} for {duration} ticks"


@perturbation(
    "rain",
    description="Wet roads: cars move less often.",
    params={
        "speed": {"type": "float", "default": 0.6, "min": 0.2, "max": 1.0, "label": "Speed factor"},
        "duration": _DUR,
    },
)
def rain(world: World, rng: random.Random, speed: float, duration: int) -> str:
    world.add_effect("speed", duration, speed, label="rain")
    return f"Rain slows traffic to x{speed:.2f} for {duration} ticks"
