"""Simulation engine: tick loop, plugin loading, external inputs, projections, replay.

Composition layer: depends on ``core``, ``llm`` and ``library``; knows nothing about HTTP or the CLI.
"""

from simulacrum.engine.plugins import ENTRY_POINT_GROUP, discover_entry_point_plugins, load_plugins
from simulacrum.engine.replay import LOG_VERSION
from simulacrum.engine.simulator import Engine

__all__ = ["ENTRY_POINT_GROUP", "LOG_VERSION", "Engine", "discover_entry_point_plugins", "load_plugins"]
