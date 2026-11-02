"""What can be simulated and what a spec may reference."""

from __future__ import annotations

from fastapi import APIRouter

from simulacrum.api.deps import RepoDep
from simulacrum.api.schemas import Components, EcosystemInfo
from simulacrum.core.registry import actions, brains, env_agents, generators, perturbations, systems

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/ecosystems", response_model=list[EcosystemInfo])
def list_ecosystems(repo: RepoDep) -> list[dict[str, object]]:
    return repo.list()


@router.get("/components", response_model=Components)
def components() -> Components:
    """Registered extension points. Plugins extend these lists."""
    return Components(
        brains=brains.names(),
        actions=actions.names(),
        systems=systems.names(),
        environment_agents=env_agents.names(),
        generators=generators.names(),
        perturbations=perturbations.names(),
    )
