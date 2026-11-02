"""Read-only projections of an engine: the JSON snapshot for the UI and an ASCII renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulacrum.engine.simulator import Engine


def snapshot(engine: Engine, history: int = 400, events: int = 60) -> dict[str, Any]:
    w = engine.world
    agents = []
    for a in w.alive_agents():
        attrs = {k: v for k, v in a.attrs.items() if isinstance(v, (str, int, float, bool)) and not k.startswith("_")}
        agents.append(
            {"id": a.id, "type": a.type, "x": a.x, "y": a.y, "energy": round(a.energy, 2), "age": a.age, "attrs": attrs}
        )
    aff = sorted(w.affinity.items(), key=lambda kv: -abs(kv[1]))[:40]
    rel = []
    for (a_id, b_id), v in aff:
        src, dst = w.agents.get(a_id), w.agents.get(b_id)
        if src and dst and src.alive and dst.alive:
            rel.append({"a": a_id, "b": b_id, "a_name": w.name_of(src), "b_name": w.name_of(dst), "value": v})
    return {
        "tick": w.tick,
        "w": w.w,
        "h": w.h,
        "hash": w.state_hash(),
        "terrain_names": w.terrain_names,
        "terrain": [w.terrain_names.index(t) for t in w.terrain],
        "terrains": {
            n: {"glyph": t.glyph, "color": t.color, "passable": t.passable}
            for n, t in engine.spec.environment.terrains.items()
        },
        "fields": {n: [round(v, 2) for v in arr] for n, arr in w.fields.items()},
        "field_info": {f.name: {"max": f.max, "color": f.color} for f in engine.spec.environment.fields},
        "types": {t.name: {"glyph": t.glyph, "color": t.color, "tier": t.tier} for t in engine.spec.agent_types},
        "agents": agents,
        "counts": {t: w.count(t) for t in w.types},
        "counters": dict(sorted(w.counters.items())),
        "globals": {k: v for k, v in w.globals.items() if isinstance(v, (str, int, float, bool))},
        "effects": [
            {
                "kind": e.kind,
                "label": e.label,
                "x": e.x,
                "y": e.y,
                "radius": e.radius,
                "until": e.until,
                "value": e.value,
            }
            for e in w.effects
        ],
        "relations": rel,
        "history": engine.history[-history:],
        "events": list(w.events)[-events:],
        "pending": [{"tick": p["tick"], "name": p["name"]} for p in engine.pending],
    }


def render_ascii(engine: Engine, field: str | None = None) -> str:
    w = engine.world
    shades = " .:-=+*#%@"
    grid = []
    for y in range(w.h):
        row = []
        for x in range(w.w):
            if field:
                mx = next((f.max for f in engine.spec.environment.fields if f.name == field), 1)
                v = w.field_at(field, x, y) / (mx or 1)
                row.append(shades[min(len(shades) - 1, int(v * (len(shades) - 1)))])
            else:
                row.append(w.terrain_spec(x, y).glyph[:1] or ".")
        grid.append(row)
    for a in w.alive_agents():
        glyph = a.attrs.get("glyph") or w.types[a.type].glyph
        grid[a.y][a.x] = str(glyph)[:1]
    counts = " ".join(f"{t}={w.count(t)}" for t in w.types)
    head = f"tick {w.tick}  {w.globals.get('season', '')}  {counts}"
    legend = "  ".join(f"{t.glyph}={t.name}" for t in engine.spec.agent_types)
    return "\n".join([head, *("".join(r) for r in grid), legend])
