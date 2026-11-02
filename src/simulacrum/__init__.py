"""Simulacrum: an extensible, replayable world simulator.

Public API (everything else is internal and may change):

    from simulacrum import Engine, load_spec
    spec, base = load_spec("forest.json")
    engine = Engine(spec, base_dir=base)
    engine.run(200)

Layering (enforced by ``tests/unit/test_architecture.py``)::

    cli, api  ->  engine  ->  library  ->  core, llm  ->  errors, config
"""

from __future__ import annotations

from simulacrum._version import __version__
from simulacrum.config import Settings
from simulacrum.core.registry import (
    actions,
    brains,
    env_agents,
    generators,
    perturbation,
    perturbations,
    systems,
)
from simulacrum.core.spec import EcosystemSpec
from simulacrum.engine import Engine, load_plugins
from simulacrum.errors import SimulacrumError
from simulacrum.llm import AnthropicProvider, GeminiProvider, StubProvider, make_provider
from simulacrum.repository import load_spec

__all__ = [
    "AnthropicProvider",
    "EcosystemSpec",
    "Engine",
    "GeminiProvider",
    "Settings",
    "SimulacrumError",
    "StubProvider",
    "__version__",
    "actions",
    "brains",
    "env_agents",
    "generators",
    "load_plugins",
    "load_spec",
    "make_provider",
    "perturbation",
    "perturbations",
    "systems",
]
