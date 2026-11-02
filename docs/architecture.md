# Architecture

## Layers and the dependency rule

```
        cli ─────────┐      ┌───────── api  (FastAPI, static UI)
                     ▼      ▼
                    engine        tick loop, plugin loading, external inputs, views, replay
                       │
                    library       built-in brains, actions, systems, generators, perturbations
                  ┌────┴────┐
                core       llm    spec/registry/world  |  providers, recording, replay
                  └────┬────┘
              errors · config     leaf modules, import nothing from the package
```

Imports point **downwards only**. `repository` (ecosystem files on disk) sits beside `engine` and may use
`core` and `errors`. The rule is enforced by `tests/unit/test_architecture.py`, which parses every module's
imports; a new top-level module must be assigned to a layer in that test, and absolute imports are mandatory.

| Package / module | Responsibility | May import |
|---|---|---|
| `errors`, `config`, `_version` | domain exceptions, `Settings` (env), version | nothing |
| `core` | `EcosystemSpec` (pydantic), the six `Registry` objects, `World` state, `state_hash()` | `errors` |
| `llm` | provider protocol, stub, Anthropic, recording/replay wrappers, factory | `errors`, `config` |
| `library` | the standard components, registered through the same decorators a plugin uses | `core`, `llm`, `errors` |
| `repository` | list/load ecosystem files from the operator directory, path-escape safe | `core`, `errors` |
| `engine` | `Engine` (tick loop), plugin loader, input catalog + validation, snapshot/ASCII views, run log + verify | `core`, `llm`, `library`, `errors` |
| `api` | app factory, routers, schemas, session store, DI, request-id/logging middleware | `engine` and below |
| `cli` | `run`, `serve`, `validate`, `verify` | `engine`, `api` and below |
| `web/static` | `index.html`, `app.css`, `app.js` (no build step) | n/a |
| `ecosystems` | bundled example worlds and their plugins (data, not a Python package) | `core`, `llm` (public extension points only) |

## Spec hierarchy

```
ecosystem
 ├─ environment      terrains, fields (continuous layers), generator, environment agents
 ├─ agent_types      brain + params, body (energy, habitat, exclusivity), reproduction, initial population, tier
 ├─ relationships    type-level rules: "eats" (gain, success, refuge by terrain), "affinity", any kind a brain reads
 ├─ systems          per-tick rules, "pre" or "post" phase
 └─ perturbations    which external inputs this ecosystem accepts
```

Type-level rules live in the spec; instance-level relations (who trusts whom) live in `world.affinity` and change
as agents act.

## Tick pipeline (`engine/simulator.py`)

1. apply due perturbations (external inputs queued for this tick)
2. environment agents (season, weather, signal controller)
3. "pre" systems (growth, spawners)
4. agents decide and act: brain → action dicts → action functions, in a seeded-shuffled order
5. "post" systems (metabolism, reproduction, economy)
6. expire effects, remove the dead, record history, optional narration

## Determinism contract

* One `random.Random(spec.seed)` is the only randomness source. Stub LLM output is a hash of `(key, tick)`.
* Every LLM response is recorded by `(tick, key)`; external inputs are logged with their tick.
* `state_hash()` covers tick, terrain, fields, agents, affinities, globals and RNG state.
* `Engine.verify(log)` replays from the log in a fresh engine and compares hashes. A replay that asks for an
  unrecorded decision reports divergence instead of calling a model.

Anything a plugin does must respect this contract (no wall-clock time, no global RNG, no iteration over unordered
sets that affects outcomes), otherwise `verify` will — correctly — fail.

## Trust model

| Source | Can run Python? | Notes |
|---|---|---|
| Files in `SIMULACRUM_ECOSYSTEMS_DIR` (`"plugins": ["x.py"]`) | yes | operator-controlled; paths escaping the directory are refused |
| `simulacrum.plugins` entry points | yes | installed distributions; loaded once at startup |
| Inline specs posted to the API | no | declarative only; `plugins` is rejected; size caps; may reference registered components |

A plugin is arbitrary code with the server's privileges. Treat the ecosystems directory like deployed code.

## Decisions and their costs

* **In-memory sessions, single process.** Simple and the run log already makes a session reproducible. Cost: no
  horizontal scaling, sessions vanish on restart.
* **Python plugins instead of a sandboxed DSL.** Maximum expressiveness for new domains (traffic, markets).
  Cost: plugins are trusted code; untrusted multi-tenant use would need process isolation first.
* **stdlib HTTP for the hosted-model providers (Anthropic, Gemini).** No extra dependency; both share one base class
  (`llm/http.py`) for the call budget, the offline fallback and log hygiene. Cost: no streaming, retries or SDK
  conveniences; failures, blocked or empty replies fall back to the offline stub (logged as warnings).
* **Pure Python grid.** Readable and deterministic. Cost: roughly 100 ticks/s on the bundled worlds; thousands of
  agents would need vectorisation or a different engine core.
* **Vanilla JS UI without a build step.** Zero toolchain, ships inside the wheel. Cost: no component framework or
  type checking for the front end.
