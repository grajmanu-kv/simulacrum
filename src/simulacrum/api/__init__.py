"""HTTP API (FastAPI) and the static web UI. Application layer: translates HTTP to engine calls."""

from simulacrum.api.app import create_app

__all__ = ["create_app"]
