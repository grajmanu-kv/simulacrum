"""The tick loop.

Tick pipeline:
    1. apply due perturbations (user-injected external inputs)
    2. environment agents   (weather, seasons, signals ...)
    3. "pre" systems        (growth, spawners ...)
    4. agents decide + act  (brains -> actions), in a seeded-shuffled order
    5. "post" systems       (metabolism, reproduction, economy ...)
    6. expire effects, bury the dead, record history, optional narration

Determinism contract: one seeded ``random.Random`` is the only source of randomness; LLM responses
are recorded by (tick, key). See ``simulacrum.engine.replay``.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any

import simulacrum.library  # noqa: F401  (registers the built-in components)
from simulacrum.core.registry import actions, brains, env_agents, generators, perturbations, systems
from simulacrum.core.spec import EcosystemSpec
from simulacrum.core.world import World
from simulacrum.engine import views
from simulacrum.engine.inputs import build_catalog, coerce_params
from simulacrum.engine.plugins import load_plugins
from simulacrum.engine.replay import export_log, verify_log
from simulacrum.errors import PerturbationError, UnknownComponentError
from simulacrum.llm import (
    LLMProvider,
    LLMRequest,
    RecordingProvider,
    ReplayProvider,
    StubProvider,
)

log = logging.getLogger(__name__)


class Engine:
    def __init__(
        self,
        spec: EcosystemSpec,
        base_dir: Path | None = None,
        llm: LLMProvider | None = None,
        replay: dict[str, Any] | None = None,
        plugin_root: Path | None = None,
    ):
        self.spec = spec
        self.base_dir = base_dir
        load_plugins(spec.plugins, base_dir, plugin_root)
        self.rng = random.Random(spec.seed)
        self.world = World(spec, self.rng)
        self.replaying = replay is not None
        self.provider: RecordingProvider | ReplayProvider
        if replay is not None:
            self.provider = ReplayProvider(replay.get("llm", []))
        else:
            self.provider = RecordingProvider(llm or StubProvider())
        self.world.llm = self.provider
        self._pending: list[dict[str, Any]] = []
        self.perturbation_log: list[dict[str, Any]] = []
        if replay is not None:
            self._pending = [dict(p) for p in replay.get("perturbations", [])]
            self.perturbation_log = [dict(p) for p in self._pending]
        self.history: list[dict[str, Any]] = []
        self._last_narration = 0

        env = spec.environment
        self._brains = {t.name: (brains.get(t.brain), t.brain_params) for t in spec.agent_types}
        self._env = [(env_agents.get(c.kind), c.params) for c in env.agents]
        self._pre = [(systems.get(c.kind), c.params) for c in spec.systems if c.phase == "pre"]
        self._post = [(systems.get(c.kind), c.params) for c in spec.systems if c.phase == "post"]
        for name in spec.perturbations:
            if name not in perturbations:
                raise UnknownComponentError(
                    f"spec lists unknown perturbation {name!r}; registered: {perturbations.names()}"
                )

        generators.get(env.generator.kind)(self.world, self.rng, **env.generator.params)
        self._init_fields()
        self._place_initial_agents()
        self._record_history()
        log.debug("engine ready: %s seed=%s %sx%s", spec.name, spec.seed, self.world.w, self.world.h)

    # ----- setup ------------------------------------------------------------------
    def _init_fields(self) -> None:
        w = self.world
        for f in self.spec.environment.fields:
            arr = w.fields[f.name]
            for i, tname in enumerate(w.terrain):
                cap = self.spec.environment.terrains[tname].capacity
                arr[i] = f.init_fraction_of_capacity * cap if f.init_fraction_of_capacity is not None else f.init

    def _place_initial_agents(self) -> None:
        w = self.world
        for t in self.spec.agent_types:
            n = t.initial.count
            if n == 0:
                continue
            allowed = set(t.initial.terrains) if t.initial.terrains else None
            cells = [
                (x, y)
                for y in range(w.h)
                for x in range(w.w)
                if w.can_enter_type(t.name, x, y) and (allowed is None or w.terrain_at(x, y) in allowed)
            ]
            if not cells:
                w.emit("setup", f"No valid habitat for {t.name}; none placed", level="warn")
                continue
            for _ in range(n):
                for _try in range(20):
                    x, y = self.rng.choice(cells)
                    if w.can_enter_type(t.name, x, y):
                        w.spawn(t.name, x, y)
                        break

    # ----- perturbations ----------------------------------------------------------
    @property
    def pending(self) -> list[dict[str, Any]]:
        """External inputs queued but not yet applied."""
        return self._pending

    def perturbation_catalog(self) -> list[dict[str, Any]]:
        return build_catalog(self.spec, self.world)

    def perturb(self, name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Queue an external input; it is applied at the start of the next tick and logged for replay."""
        if self.replaying:
            raise PerturbationError("cannot inject perturbations into a replay")
        clean = coerce_params(self.perturbation_catalog(), name, params or {})
        entry = {"tick": self.world.tick + 1, "name": name, "params": clean}
        self._pending.append(entry)
        self.perturbation_log.append(dict(entry))
        return entry

    def _apply_due(self) -> None:
        w = self.world
        due = [p for p in self._pending if p["tick"] <= w.tick]
        self._pending = [p for p in self._pending if p["tick"] > w.tick]
        for p in due:
            msg = perturbations.get(p["name"]).apply(w, self.rng, **p["params"])
            w.emit("perturbation", msg or p["name"], level="major")

    # ----- stepping ---------------------------------------------------------------
    def step(self) -> None:
        w = self.world
        w.tick += 1
        w.metrics = {}
        self._apply_due()
        for fn, params in self._env:
            fn(w, self.rng, **params)
        for fn, params in self._pre:
            fn(w, self.rng, **params)
        order = [a.id for a in w.agents.values() if a.alive]
        self.rng.shuffle(order)
        for aid in order:
            a = w.agents.get(aid)
            if a is None or not a.alive:
                continue
            brain, bparams = self._brains[a.type]
            acts = brain(w, a, self.rng, **bparams)
            if acts is None:
                continue
            if isinstance(acts, dict):
                acts = [acts]
            for act in acts:
                if not a.alive:
                    break
                actions.get(act["op"])(w, a, act, self.rng)
        for a in w.agents.values():
            if a.alive:
                a.age += 1
        for fn, params in self._post:
            fn(w, self.rng, **params)
        w.effects = [e for e in w.effects if e.until >= w.tick]
        for aid in [i for i, a in w.agents.items() if not a.alive]:
            del w.agents[aid]
        self._record_history()
        self._maybe_narrate()

    def run(self, n: int) -> None:
        for _ in range(n):
            self.step()

    def _record_history(self) -> None:
        w = self.world
        row = {
            "t": w.tick,
            "counts": {t: w.count(t) for t in w.types},
            "fields": {n: round(sum(v) / len(v), 4) for n, v in w.fields.items()},
            "metrics": {k: round(v, 3) for k, v in w.metrics.items()},
        }
        self.history.append(row)
        if len(self.history) > 3000:
            self.history = self.history[-2000:]

    def _maybe_narrate(self) -> None:
        w, n = self.world, self.spec.narrate_every
        if not n or w.tick % n:
            return
        recent = [e for e in w.events if e["t"] > self._last_narration and e["kind"] != "narrative"]
        self._last_narration = w.tick
        ctx = {
            "kind": "narration",
            "tick": w.tick,
            "season": w.globals.get("season"),
            "counts": {t: w.count(t) for t in w.types},
            "events": recent[-12:],
        }
        prompt = f"You narrate a living world in 1-2 sentences, concrete and unsentimental. State: {ctx}"
        text = w.llm.complete(LLMRequest(w.tick, "narrator", "You are the world's chronicler.", prompt, ctx))
        w.emit("narrative", text.strip()[:400], level="story")

    # ----- views & replay (thin delegates; the logic lives in views.py / replay.py) ----
    def snapshot(self, history: int = 400, events: int = 60) -> dict[str, Any]:
        return views.snapshot(self, history, events)

    def render_ascii(self, field: str | None = None) -> str:
        return views.render_ascii(self, field)

    def export_log(self) -> dict[str, Any]:
        return export_log(self)

    @classmethod
    def verify(
        cls, log: dict[str, Any], base_dir: Path | None = None, plugin_root: Path | None = None
    ) -> dict[str, Any]:
        """Re-run a logged session from its spec, perturbations and recorded LLM responses."""

        def make(lg: dict[str, Any]) -> Engine:
            return cls(EcosystemSpec.model_validate(lg["spec"]), base_dir=base_dir, replay=lg, plugin_root=plugin_root)

        return verify_log(log, make)
