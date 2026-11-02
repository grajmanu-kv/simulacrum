# Simulacrum

An extensible world simulator with a web UI. Describe a world declaratively (terrain, resources, species,
relationships, rules), generate it from a seed, watch it develop tick by tick, and push on it from outside
(weather, infrastructure, introduced species). A few high-level actors can take their decisions from an LLM;
everything else is plain code. Every run is reproducible: same seed and same inputs give the same world.

```
pip install -e ".[dev]"
simulacrum serve                   # UI at http://127.0.0.1:8000
simulacrum run src/simulacrum/ecosystems/forest.json --ticks 200 --every 50
simulacrum validate my_world.json  # check a spec and its references
simulacrum verify run.json         # replay a run log, compare state hashes
make check                         # lint, types, tests with coverage gate
```

Scale is yours to choose: the same engine runs an island with food webs and tribes, or a signalised
road junction with cars (`src/simulacrum/ecosystems/junction_plugin.py`, a plugin that touches no engine code).
The smallest bundled world is `garden.json`: two people and a god.

## How it is organised

```
simulacrum/
├── pyproject.toml            packaging, entry points, ruff / mypy / pytest / coverage config
├── Makefile                  install, lint, format, typecheck, test, cov, check, serve, build, docker
├── Dockerfile  .dockerignore multi-stage, non-root, healthcheck
├── .github/workflows/ci.yml  lint + types, tests on py3.10-3.13, wheel-content check, image build
├── .env.example  .editorconfig  .gitignore
├── CHANGELOG.md  CONTRIBUTING.md
├── docs/                     architecture.md  extending.md  api.md  operations.md
├── src/simulacrum/
│   ├── errors.py             domain exceptions (also subclass the matching builtin)
│   ├── config.py             Settings from SIMULACRUM_* env vars, logging setup
│   ├── repository.py         load / list ecosystem files (path-escape safe)
│   ├── core/                 spec.py  registry.py  world.py
│   ├── llm/                  base.py  stub.py  anthropic.py  replay.py  factory.py
│   ├── library/              generators  environment  systems  actions  brains  factions  perturbations  movement
│   ├── engine/               simulator.py  plugins.py  inputs.py  views.py  replay.py
│   ├── api/                  app.py  deps.py  schemas.py  sessions.py  routers/{health,catalog,sessions,ui}.py
│   ├── cli/                  main.py
│   ├── web/static/           index.html  app.css  app.js
│   └── ecosystems/           forest, junction, garden (.json) + junction_plugin.py, garden_plugin.py
└── tests/
    ├── conftest.py
    ├── unit/                 architecture, config, errors/registry, spec, llm, inputs, plugins, repository
    └── integration/          determinism+replay, forest, junction, extensibility, llm tier, api, cli
```

Dependencies point downwards only (`cli`/`api` → `engine` → `library` → `core`/`llm` → `errors`/`config`), and a
test enforces it. Details: [architecture](docs/architecture.md).

## Documentation

* [Architecture](docs/architecture.md): layers, spec hierarchy, tick pipeline, determinism, trust model, trade-offs
* [Extending](docs/extending.md): write brains, actions, systems, generators, perturbations; plugins and entry points
* [HTTP API](docs/api.md): endpoints, status codes, sessions
* [Operations](docs/operations.md): configuration, running, observability, security checklist
* [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Status and honest limits

* Alpha. Sessions are in memory and the server has no authentication: run one worker, behind your own gateway
  (see the security checklist before exposing it).
* The forest's predator-prey balance is tuned, not inevitable: with the default seed all three trophic levels persist for
  600 ticks, but in a 5-seed check only 3 seeds did (hunters died out in the others). Extinction is an outcome, not a bug.
* The Claude-backed faction council is implemented, budgeted and falls back to the offline heuristic on any failure,
  but it has not been exercised against the live API. Its output is generated fiction, not evidence about societies.
* The junction has no collision model, so a "signals all green" fault can raise throughput.
* Pure-Python grid, roughly 100 ticks/s on the bundled worlds. UI tested in headless Chrome only.
* No `LICENSE` file is included; choose one before publishing.
