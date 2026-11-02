"""External inputs: the catalog a spec exposes (also drives the UI form) and parameter validation."""

from __future__ import annotations

from typing import Any

from simulacrum.core.registry import perturbations
from simulacrum.core.spec import EcosystemSpec
from simulacrum.core.world import World
from simulacrum.errors import PerturbationError


def build_catalog(spec: EcosystemSpec, world: World) -> list[dict[str, Any]]:
    """Perturbations enabled for this ecosystem, with ``@terrains`` / ``@agent_types`` choices resolved
    and map-coordinate bounds filled in."""
    out = []
    for name in spec.perturbations or perturbations.names():
        d = perturbations.get(name)
        params: dict[str, Any] = {}
        for k, p in d.params.items():
            p = dict(p)
            if p.get("choices") == "@terrains":
                p["choices"] = list(spec.environment.terrains)
            elif p.get("choices") == "@agent_types":
                p["choices"] = [t.name for t in spec.agent_types]
            if p.get("type") == "choice" and "default" not in p and p.get("choices"):
                p["default"] = p["choices"][0]
            if p.get("role") == "x":
                p.setdefault("min", 0)
                p["max"] = world.w - 1
            if p.get("role") == "y":
                p.setdefault("min", 0)
                p["max"] = world.h - 1
            params[k] = p
        out.append({"name": d.name, "label": d.label, "description": d.description, "params": params})
    return out


def coerce_params(catalog: list[dict[str, Any]], name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and clamp user-supplied parameters. Never trusts the client: unknown keys and bad choices raise."""
    by_name = {c["name"]: c for c in catalog}
    if name not in by_name:
        raise PerturbationError(f"perturbation {name!r} is not enabled for this ecosystem")
    out: dict[str, Any] = {}
    for k, p in by_name[name]["params"].items():
        v = raw.get(k, p.get("default"))
        t = p.get("type", "float")
        if t == "int":
            v = round(float(v))
        elif t == "float":
            v = float(v)
        elif t == "choice" and v not in p["choices"]:
            raise PerturbationError(f"{k}={v!r} not in {p['choices']}")
        if t in ("int", "float"):
            if "min" in p:
                v = max(p["min"], v)
            if "max" in p:
                v = min(p["max"], v)
        out[k] = v
    extra = set(raw) - set(out)
    if extra:
        raise PerturbationError(f"unknown parameters for {name}: {sorted(extra)}")
    return out
