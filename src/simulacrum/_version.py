"""Single source of the package version (the installed distribution metadata)."""

from __future__ import annotations

from importlib import metadata

try:
    __version__ = metadata.version("simulacrum")
except metadata.PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"
