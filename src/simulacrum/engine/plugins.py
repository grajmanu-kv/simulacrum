"""Plugin loading.

Two sources, with different trust levels:

* **File plugins** (``"plugins": ["junction_plugin.py"]`` in a spec) are loaded from inside the
  operator-controlled ecosystems directory. Paths that escape it are refused.
* **Entry-point plugins** (``simulacrum.plugins`` group) come from installed distributions and are
  loaded once at startup by the operator; specs cannot name them.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from importlib import metadata
from pathlib import Path
from types import ModuleType

from simulacrum.errors import PluginLoadError, PluginSecurityError

log = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "simulacrum.plugins"
_FILE_CACHE: dict[tuple[str, float], ModuleType] = {}


def load_plugins(refs: list[str], base_dir: Path | None, root: Path | None = None) -> None:
    """Import plugin modules. A ref ending in .py is a file under `base_dir`; anything else is a module name.
    When `root` is given, file plugins must live under it."""
    for ref in refs:
        if ref.endswith(".py"):
            _load_file(ref, base_dir, root)
        else:
            try:
                importlib.import_module(ref)
            except ImportError as e:
                raise PluginLoadError(f"cannot import plugin module {ref!r}: {e}") from e


def _load_file(ref: str, base_dir: Path | None, root: Path | None) -> None:
    p = (Path(base_dir or ".") / ref).resolve()
    if root is not None and not p.is_relative_to(root.resolve()):
        raise PluginSecurityError(f"plugin {ref!r} is outside the allowed directory")
    if not p.is_file():
        raise PluginLoadError(f"plugin file {ref!r} not found")
    key = (str(p), p.stat().st_mtime)
    if key in _FILE_CACHE:
        return
    modname = f"simulacrum_plugin_{p.stem}"
    spec = importlib.util.spec_from_file_location(modname, p)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"cannot load plugin {p}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    _FILE_CACHE[key] = mod
    log.info("loaded plugin file %s", p.name)


def discover_entry_point_plugins() -> list[str]:
    """Import every ``simulacrum.plugins`` entry point; a broken one is logged and skipped, not fatal."""
    loaded: list[str] = []
    for ep in metadata.entry_points(group=ENTRY_POINT_GROUP):
        try:
            ep.load()
        except Exception:
            log.exception("entry-point plugin %s failed to load; skipping", ep.name)
            continue
        loaded.append(ep.name)
        log.info("loaded entry-point plugin %s", ep.name)
    return loaded
