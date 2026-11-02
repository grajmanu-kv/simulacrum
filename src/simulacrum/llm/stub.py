"""Offline, deterministic provider: a trait-driven heuristic standing in for a faction council."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar

from simulacrum.llm.base import LLMRequest


def _unit(*parts: Any) -> float:
    """Deterministic pseudo-random float in [0, 1) from arbitrary parts (no RNG state consumed)."""
    d = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(d[:8], "big") / 2**64


StubResponder = Callable[[dict[str, Any], float], dict[str, Any]]
R = TypeVar("R", bound=StubResponder)
_RESPONDERS: dict[str, StubResponder] = {}


def register_stub_responder(kind: str) -> Callable[[R], R]:
    """Let a plugin supply the offline (stub) answer for requests whose ``context["kind"]`` is `kind`.

    The responder gets ``(context, u)`` where ``u`` is a deterministic float in [0, 1) derived from the request key
    and tick, and returns the JSON-serialisable reply a model would give. Requests of unregistered kinds keep the
    default faction heuristic.
    """

    def deco(fn: R) -> R:
        _RESPONDERS[kind] = fn
        return fn

    return deco


def stub_decide(ctx: dict[str, Any], u: float) -> dict[str, Any]:
    """Offline stand-in for a faction council. Trait-driven heuristic, deterministic."""
    pop, food, trait = ctx["pop"], ctx["food"], ctx.get("trait", "peaceful")
    nbrs = ctx.get("neighbors", [])
    need = pop * 1.2
    friendly = [n for n in nbrs if n["affinity"] > -0.15]
    rich = [n for n in nbrs if n["food"] > food * 1.2 and n["affinity"] < 0.3]
    weaker = [n for n in nbrs if n["pop"] < pop and n["affinity"] < 0.1]
    if food > pop * 4 and pop >= 12:
        return {"stance": "found", "say": "Our numbers swell; a daughter settlement will be founded."}
    if food < need:
        if trait == "aggressive" and rich and u < 0.6:
            return {"stance": "raid", "target": rich[0]["id"], "say": f"We take what {rich[0]['name']} hoards."}
        if ctx["local_plants"] >= 0.22:
            return {"stance": "forage", "say": "The fields still give; we gather."}
        if ctx["local_prey"] >= 2 and u < 0.5:
            return {"stance": "hunt", "say": "Game is near; the hunters go out."}
        return {"stance": "migrate", "say": "The land here is spent; we move on."}
    if friendly and trait in ("peaceful", "cunning") and u < 0.5:
        return {"stance": "trade", "target": friendly[0]["id"], "say": f"We send envoys to {friendly[0]['name']}."}
    if trait == "aggressive" and weaker and u < 0.3:
        return {"stance": "raid", "target": weaker[0]["id"], "say": f"{weaker[0]['name']} is weak; we strike."}
    if ctx["local_prey"] >= 3 and u < 0.35:
        return {"stance": "hunt", "say": "A good season for the hunt."}
    return {"stance": "forage", "say": "We tend and gather."}


def stub_narrate(ctx: dict[str, Any]) -> str:
    counts = ", ".join(f"{n} {k}" for k, n in sorted(ctx.get("counts", {}).items()))
    notable = [
        e
        for e in ctx.get("events", [])
        if e["kind"] in ("raid", "faction", "perturbation", "weather", "god", "quarrel", "kindness")
    ]
    tail = f" Notable: {notable[-1]['text']}." if notable else ""
    return f"Tick {ctx.get('tick')}, {ctx.get('season', 'unknown season')}: {counts}.{tail}"


class StubProvider:
    name = "stub"

    def complete(self, req: LLMRequest) -> str:
        if req.context.get("kind") == "narration":
            return stub_narrate(req.context)
        responder = _RESPONDERS.get(str(req.context.get("kind")))
        if responder is not None:
            return json.dumps(responder(req.context, _unit(req.key, req.tick)))
        return json.dumps(stub_decide(req.context, _unit(req.key, req.tick)))
