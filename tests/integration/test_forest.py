from __future__ import annotations

from collections.abc import Callable

from simulacrum import Engine


def test_drought_depresses_plants_only_where_applied(forest: Callable[..., Engine]) -> None:
    ctl, exp = forest(7), forest(7)
    ctl.run(5), exp.run(5)
    exp.perturb("drought", {"x": 28, "y": 18, "radius": 6, "duration": 40, "intensity": 0.9})
    ctl.run(30), exp.run(30)

    def mean(e: Engine, inside: bool) -> float:
        w = e.world
        vals = [
            w.field_at("plants", x, y)
            for y in range(w.h)
            for x in range(w.w)
            if w.terrain_spec(x, y).capacity > 0.5 and (((x - 28) ** 2 + (y - 18) ** 2 <= 36) == inside)
        ]
        return sum(vals) / len(vals)

    assert mean(exp, True) < 0.6 * mean(ctl, True)
    assert mean(exp, False) > 0.7 * mean(ctl, False)  # far-field is not wiped out


def test_terraform_introduce_flood(forest: Callable[..., Engine]) -> None:
    e = forest(7)
    e.perturb("terraform", {"x": 28, "y": 18, "radius": 2, "terrain": "road"})
    n0 = e.world.count("hunter")
    e.perturb("introduce", {"type": "hunter", "x": 28, "y": 18, "radius": 8, "count": 5})
    e.step()
    assert e.world.terrain_at(28, 18) == "road"
    assert e.world.count("hunter") >= n0 + 3
    e.perturb("flood", {"x": 28, "y": 18, "radius": 5, "duration": 10})
    e.step()
    assert e.world.effect_sum("blocked", 28, 18) > 0
    assert e.world.field_at("plants", 28, 18) == 0.0


def test_generator_makes_varied_deterministic_terrain(forest: Callable[..., Engine]) -> None:
    a, b = forest(7), forest(7)
    assert a.world.terrain == b.world.terrain
    assert {"water", "grass", "forest"} <= set(a.world.terrain)
    assert forest(8).world.terrain != a.world.terrain


def test_default_forest_keeps_all_trophic_levels(forest: Callable[..., Engine]) -> None:
    e = forest(7)
    e.run(500)
    assert all(e.world.count(t) > 0 for t in ("grazer", "hunter", "tribe"))
    c = e.world.counters
    assert c.get("predation", 0) > 0 and c.get("raids", 0) > 0 and c.get("settlements_founded", 0) > 0
