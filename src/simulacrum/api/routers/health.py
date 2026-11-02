"""Liveness, readiness and version: what an orchestrator or load balancer probes."""

from __future__ import annotations

from fastapi import APIRouter

from simulacrum._version import __version__
from simulacrum.api.deps import RepoDep, SettingsDep, StoreDep
from simulacrum.api.schemas import Health, Readiness, VersionInfo

router = APIRouter(tags=["ops"])


@router.get("/healthz", response_model=Health)
def healthz() -> Health:
    """Liveness: the process is up and serving."""
    return Health(status="ok")


@router.get("/readyz", response_model=Readiness)
def readyz(repo: RepoDep, store: StoreDep, settings: SettingsDep) -> Readiness:
    """Readiness: the ecosystems directory is readable."""
    ok = repo.exists()
    return Readiness(
        status="ready" if ok else "degraded", ecosystems_dir=ok, sessions=len(store), max_sessions=settings.max_sessions
    )


@router.get("/api/version", response_model=VersionInfo)
def version() -> VersionInfo:
    return VersionInfo(version=__version__)
