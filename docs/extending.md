# Extending Simulacrum

Everything a world can do is a named entry in one of six registries (`simulacrum.core.registry`). Specs refer to
entries by name; plugins add entries with decorators. Built-in components use exactly the same mechanism.

| Registry | Signature | Used by |
|---|---|---|
| `brains` | `fn(world, agent, rng, **brain_params) -> action \| [actions] \| None` | `agent_types[].brain` |
| `actions` | `fn(world, agent, action: dict, rng) -> None` | the `op` key of a brain's action |
| `systems` | `fn(world, rng, **params) -> None` | `systems[]`, phase `pre` or `post` |
| `env_agents` | `fn(world, rng, **params) -> None` | `environment.agents[]` |
| `generators` | `fn(world, rng, **params) -> None` (fill `world.terrain`) | `environment.generator` |
| `perturbations` | `@perturbation(name, params={...})` → `fn(world, rng, **params) -> str` | `perturbations[]` |

## Write a plugin

```python
# my_world_plugin.py  (put it next to your spec in the ecosystems directory)
import random
from simulacrum.core.registry import brains, perturbation
from simulacrum.core.world import Agent, World


@brains.register("pedestrian")
def pedestrian(world: World, a: Agent, rng: random.Random, speed: float = 1.0):
    return {"op": "move", "dx": rng.choice((-1, 0, 1)), "dy": 1}


@perturbation(
    "closure",
    description="Close a street for a while.",
    params={
        "x": {"type": "int", "role": "x"},
        "y": {"type": "int", "role": "y"},
        "duration": {"type": "int", "default": 30, "min": 1, "max": 300},
    },
)
def closure(world: World, rng: random.Random, x: int, y: int, duration: int) -> str:
    world.add_effect("blocked", duration, 1.0, mode="add", x=x, y=y, radius=0, label="closure")
    return f"Street closed at ({x},{y}) for {duration} ticks"
```

Reference it from the spec: `"plugins": ["my_world_plugin.py"]`. See `src/simulacrum/ecosystems/junction_plugin.py`
for a complete, typed example that uses every extension point.

### Distribute a plugin as a package

```toml
# your pyproject.toml
[project.entry-points."simulacrum.plugins"]
my_world = "my_package.simulacrum_plugin"
```

The module registers its components on import. The server and CLI import every entry point at startup; a broken one
is logged and skipped. Specs cannot name entry points, only operators can install them.

## Give an LLM-driven agent an offline answer

A brain that asks the model for a decision calls `world.llm.complete(LLMRequest(tick, key, system, prompt, context))`.
Put a `"kind"` in `context` and register an offline stand-in so the world runs (and replays) without a key:

```python
from simulacrum.llm import register_stub_responder


@register_stub_responder("my_kind")
def offline(ctx: dict, u: float) -> dict:  # u: deterministic float in [0, 1) from (key, tick)
    return {"act": "wait"}
```

`garden_plugin.py` does this for its god. Parse replies defensively (`parse_json_object`, then validate every field):
model output is untrusted input.

## Perturbation parameter schema

Each `params` entry drives both server-side validation (values are clamped, unknown keys rejected) and the UI form.

| Key | Meaning |
|---|---|
| `type` | `int`, `float` or `choice` |
| `default`, `min`, `max`, `label` | as named; numeric values are clamped to `[min, max]` |
| `choices` | list, or `"@terrains"` / `"@agent_types"` resolved per ecosystem |
| `role` | `"x"` or `"y"`: filled by clicking the map; bounds come from the world size |

External inputs act on the **environment** through effects (`world.add_effect(kind, duration, value, mode, x, y,
radius, label)`; `radius=-1` is global, `0` a single cell). Systems and brains read them with
`world.effect_mult(kind, x, y)` / `world.effect_sum(kind, x, y)`. Built-in kinds: `growth`, `move_cost`, `blocked`,
`speed`, `spawn_rate`, `signal_fault`. New kinds compose with old rules for free.

## Rules for deterministic plugins

Use the `rng` you are given, never `random.*` or `time.*`; do not depend on set/dict-of-objects ordering that
changes between runs; keep decisions inside the world (`world.globals`, `agent.attrs`). Then
`simulacrum verify run.json` will reproduce your world exactly.

## Test your plugin

```python
from simulacrum import Engine, load_spec

spec, base = load_spec("my_world.json")
e = Engine(spec, base_dir=base)
e.run(100)
assert Engine.verify(e.export_log(), base_dir=base)["ok"]
```
