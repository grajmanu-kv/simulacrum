"""Built-in world generators."""

from __future__ import annotations

import math
import random

from simulacrum.core.registry import generators
from simulacrum.core.world import World


def _value_noise(
    rng: random.Random, w: int, h: int, scale: float, octaves: int = 3, persistence: float = 0.5
) -> list[float]:
    out = [0.0] * (w * h)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = max(1.0, scale / (2**o))
        gw, gh = int(w / s) + 3, int(h / s) + 3
        lat = [[rng.random() for _ in range(gw)] for _ in range(gh)]
        for y in range(h):
            fy = y / s
            iy = int(fy)
            ty = fy - iy
            ty = ty * ty * (3 - 2 * ty)
            r0, r1 = lat[iy], lat[iy + 1]
            for x in range(w):
                fx = x / s
                ix = int(fx)
                tx = fx - ix
                tx = tx * tx * (3 - 2 * tx)
                a = r0[ix] + (r0[ix + 1] - r0[ix]) * tx
                b = r1[ix] + (r1[ix + 1] - r1[ix]) * tx
                out[y * w + x] += (a + (b - a) * ty) * amp
        total += amp
        amp *= persistence
    lo, hi = min(out), max(out)
    span = (hi - lo) or 1.0
    return [(v - lo) / span for v in out]


@generators.register("noise_terrain")
def noise_terrain(
    world: World,
    rng: random.Random,
    scale: float = 10.0,
    octaves: int = 3,
    island: float = 0.0,
    bands: list | None = None,
    patches: list | None = None,
) -> None:
    """Elevation noise -> terrain bands; optional island falloff and secondary patch noise.

    bands:   [[threshold, terrain], ...] ascending; first band whose threshold exceeds elevation wins.
    patches: [{"on": terrain, "to": terrain, "scale": 6, "threshold": 0.55}] re-labels cells by a second noise field.
    """
    w, h = world.w, world.h
    names = set(world.terrain_names)
    bands = bands or [[1.01, world.terrain_names[0]]]
    for _, t in bands:
        if t not in names:
            raise ValueError(f"generator band references unknown terrain {t!r}")
    e = _value_noise(rng, w, h, scale, octaves)
    if island > 0:
        for y in range(h):
            for x in range(w):
                d = min(1.0, math.hypot((x - (w - 1) / 2) / (w / 2), (y - (h - 1) / 2) / (h / 2)))
                e[y * w + x] = e[y * w + x] * (1 - island) + (1 - d) * island
        lo, hi = min(e), max(e)
        e = [(v - lo) / ((hi - lo) or 1.0) for v in e]
    for i, v in enumerate(e):
        for thr, t in bands:
            if v < thr:
                world.terrain[i] = t
                break
        else:
            world.terrain[i] = bands[-1][1]
    for p in patches or []:
        m = _value_noise(rng, w, h, p.get("scale", 6.0), 2)
        for i, v in enumerate(m):
            if world.terrain[i] == p["on"] and v > p["threshold"]:
                world.terrain[i] = p["to"]
