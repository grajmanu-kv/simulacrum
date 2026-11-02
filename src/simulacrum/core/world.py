"""World state: grid, continuous fields, agents, effects, relationships, event feed.

The world is plain data plus small helpers. It owns ground truth; brains and systems
read and mutate it through these helpers so every run stays consistent and replayable.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from simulacrum.core.spec import AgentTypeSpec, EcosystemSpec, RelationshipSpec, TerrainSpec


class LanguageModel(Protocol):
    """The slice of an LLM provider the world needs. Defined here so ``core`` stays independent of ``llm``."""

    def complete(self, req: Any, /) -> str: ...


@dataclass
class Agent:
    id: int
    type: str
    x: int
    y: int
    energy: float
    age: int = 0
    alive: bool = True
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Effect:
    """A time-limited modifier on a region. `kind` is a free-form string that whichever
    systems/brains care will query (e.g. "growth", "move_cost", "blocked", "speed")."""

    kind: str
    value: float = 1.0
    mode: str = "mult"  # "mult" (product) or "add" (sum)
    x: int | None = None
    y: int | None = None
    radius: float = -1.0  # <0 => whole world; 0 => single cell
    until: int = 0  # last tick (inclusive) the effect is active
    label: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def covers(self, x: int, y: int) -> bool:
        if self.radius < 0 or self.x is None or self.y is None:
            return True
        return (x - self.x) ** 2 + (y - self.y) ** 2 <= self.radius**2


class World:
    def __init__(self, spec: EcosystemSpec, rng: random.Random):
        self.spec = spec
        self.rng = rng
        self.tick = 0
        env = spec.environment
        self.w, self.h = env.width, env.height
        self.terrain_names: list[str] = list(env.terrains)
        self.terrain: list[str] = [self.terrain_names[0]] * (self.w * self.h)
        self.fields: dict[str, list[float]] = {f.name: [f.init] * (self.w * self.h) for f in env.fields}
        self.types: dict[str, AgentTypeSpec] = {t.name: t for t in spec.agent_types}
        self.agents: dict[int, Agent] = {}
        self._next_id = 1
        self._index: dict[tuple[int, int], list[int]] = {}
        self._counts: dict[str, int] = dict.fromkeys(self.types, 0)
        self.effects: list[Effect] = []
        self.globals: dict[str, Any] = {}
        self.affinity: dict[tuple[int, int], float] = {}
        self.events: deque = deque(maxlen=1000)
        self.counters: dict[str, int] = {}
        self.metrics: dict[str, float] = {}
        self._llm: LanguageModel | None = None  # attached by the engine
        self._throttle: dict[Any, int] = {}
        self.rel_from: dict[str, list[RelationshipSpec]] = {}
        self.rel_to: dict[str, list[RelationshipSpec]] = {}
        for r in spec.relationships:
            self.rel_from.setdefault(r.source, []).append(r)
            self.rel_to.setdefault(r.target, []).append(r)

    # ----- geometry ---------------------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    @property
    def llm(self) -> LanguageModel:
        if self._llm is None:
            raise RuntimeError("no LLM provider attached to this world")
        return self._llm

    @llm.setter
    def llm(self, provider: LanguageModel) -> None:
        self._llm = provider

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def terrain_at(self, x: int, y: int) -> str:
        return self.terrain[self.idx(x, y)]

    def terrain_spec(self, x: int, y: int) -> TerrainSpec:
        return self.spec.environment.terrains[self.terrain[self.idx(x, y)]]

    def cells_within(self, x: int, y: int, r: float) -> Iterator[tuple[int, int]]:
        ri = math.ceil(r)
        r2 = r * r
        for cy in range(max(0, y - ri), min(self.h, y + ri + 1)):
            for cx in range(max(0, x - ri), min(self.w, x + ri + 1)):
                if (cx - x) ** 2 + (cy - y) ** 2 <= r2:
                    yield cx, cy

    # ----- fields -----------------------------------------------------------------
    def field_at(self, name: str, x: int, y: int) -> float:
        return self.fields[name][self.idx(x, y)]

    def field_mean(self, name: str, x: int, y: int, r: float) -> float:
        vals = [self.fields[name][self.idx(cx, cy)] for cx, cy in self.cells_within(x, y, r)]
        return sum(vals) / len(vals) if vals else 0.0

    # ----- effects ----------------------------------------------------------------
    def add_effect(
        self,
        kind: str,
        duration: int,
        value: float = 1.0,
        mode: str = "mult",
        x: int | None = None,
        y: int | None = None,
        radius: float = -1.0,
        label: str = "",
        **data: Any,
    ) -> Effect:
        e = Effect(kind, value, mode, x, y, radius, self.tick + max(1, duration) - 1, label or kind, data)
        self.effects.append(e)
        return e

    def effects_of(self, kind: str) -> list[Effect]:
        return [e for e in self.effects if e.kind == kind]

    def effect_mult(self, kind: str, x: int, y: int) -> float:
        out = 1.0
        for e in self.effects:
            if e.kind == kind and e.mode == "mult" and e.covers(x, y):
                out *= e.value
        return out

    def effect_sum(self, kind: str, x: int, y: int) -> float:
        return sum(e.value for e in self.effects if e.kind == kind and e.mode == "add" and e.covers(x, y))

    # ----- agents -----------------------------------------------------------------
    def count(self, type_name: str) -> int:
        return self._counts.get(type_name, 0)

    def can_enter_type(self, type_name: str, x: int, y: int, ignore_id: int | None = None) -> bool:
        if not self.in_bounds(x, y):
            return False
        if not self.terrain_spec(x, y).passable:
            return False
        t = self.types[type_name]
        if t.habitat is not None and self.terrain_at(x, y) not in t.habitat:
            return False
        if self.effect_sum("blocked", x, y) > 0:
            return False
        if t.exclusive:
            for oid in self._index.get((x, y), ()):
                if oid != ignore_id and self.types[self.agents[oid].type].exclusive:
                    return False
        return True

    def can_enter(self, a: Agent, x: int, y: int) -> bool:
        return self.can_enter_type(a.type, x, y, ignore_id=a.id)

    def spawn(
        self, type_name: str, x: int, y: int, energy: float | None = None, attrs: dict[str, Any] | None = None
    ) -> Agent | None:
        t = self.types[type_name]
        if self._counts[type_name] >= t.max_population:
            return None
        if energy is None:
            energy = t.initial.energy if t.initial.energy is not None else t.max_energy * 0.6
        a = Agent(self._next_id, type_name, x, y, float(energy))
        self._next_id += 1
        a.attrs = json.loads(json.dumps(t.attrs))  # deep copy of defaults
        for k, choices in t.attr_choices.items():
            a.attrs[k] = self.rng.choice(choices)
        if attrs:
            a.attrs.update(attrs)
        self.agents[a.id] = a
        self._index.setdefault((x, y), []).append(a.id)
        self._counts[type_name] += 1
        return a

    def kill(self, a: Agent, cause: str) -> None:
        if not a.alive:
            return
        a.alive = False
        ids = self._index.get((a.x, a.y))
        if ids and a.id in ids:
            ids.remove(a.id)
        self._counts[a.type] -= 1
        self.bump(f"deaths:{cause}")

    def move_agent(self, a: Agent, x: int, y: int) -> None:
        ids = self._index.get((a.x, a.y))
        if ids and a.id in ids:
            ids.remove(a.id)
        a.x, a.y = x, y
        self._index.setdefault((x, y), []).append(a.id)

    def agents_at(self, x: int, y: int) -> list[Agent]:
        return [self.agents[i] for i in self._index.get((x, y), ()) if self.agents[i].alive]

    def nearby(self, a: Agent, radius: float, types: list[str] | None = None) -> list[tuple[float, Agent]]:
        out: list[tuple[float, Agent]] = []
        for cx, cy in self.cells_within(a.x, a.y, radius):
            ids = self._index.get((cx, cy))
            if not ids:
                continue
            for oid in ids:
                if oid == a.id:
                    continue
                o = self.agents[oid]
                if o.alive and (types is None or o.type in types):
                    out.append((math.hypot(cx - a.x, cy - a.y), o))
        out.sort(key=lambda t: (t[0], t[1].id))
        return out

    def alive_agents(self) -> list[Agent]:
        return [a for a in self.agents.values() if a.alive]

    def name_of(self, a: Agent) -> str:
        return str(a.attrs.get("name") or f"{a.type}#{a.id}")

    # ----- relationships ----------------------------------------------------------
    def rel_param(self, source: str, kind: str, target: str, key: str, default: Any = None) -> Any:
        for r in self.rel_from.get(source, ()):
            if r.kind == kind and r.target == target:
                return r.params.get(key, default)
        return default

    def shift_affinity(self, a_id: int, b_id: int, delta: float) -> None:
        v = max(-1.0, min(1.0, self.affinity.get((a_id, b_id), 0.0) + delta))
        self.affinity[(a_id, b_id)] = round(v, 4)

    # ----- feed & counters --------------------------------------------------------
    def bump(self, counter: str, n: int = 1) -> None:
        self.counters[counter] = self.counters.get(counter, 0) + n

    def emit(
        self, kind: str, text: str, level: str = "info", throttle_key: Any = None, every: int = 0, **data: Any
    ) -> bool:
        if throttle_key is not None and every > 0:
            last = self._throttle.get(throttle_key)
            if last is not None and self.tick - last < every:
                return False
            self._throttle[throttle_key] = self.tick
        ev: dict[str, Any] = {"t": self.tick, "kind": kind, "level": level, "text": text}
        if data:
            ev["data"] = data
        self.events.append(ev)
        return True

    # ----- integrity --------------------------------------------------------------
    def state_hash(self) -> str:
        h = hashlib.sha256()
        h.update(str(self.tick).encode())
        h.update(",".join(str(self.terrain_names.index(t)) for t in self.terrain).encode())
        for name in sorted(self.fields):
            h.update(name.encode())
            h.update(",".join(f"{v:.5f}" for v in self.fields[name]).encode())
        rows = [
            [a.id, a.type, a.x, a.y, round(a.energy, 5), a.age, a.alive, a.attrs]
            for a in sorted(self.agents.values(), key=lambda a: a.id)
        ]
        h.update(json.dumps(rows, sort_keys=True, default=str).encode())
        h.update(json.dumps(sorted((list(k), v) for k, v in self.affinity.items())).encode())
        h.update(json.dumps(self.globals, sort_keys=True, default=str).encode())
        h.update(repr(self.rng.getstate()).encode())
        return h.hexdigest()[:16]
