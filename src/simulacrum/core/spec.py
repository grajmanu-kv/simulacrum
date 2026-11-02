"""Declarative ecosystem specification.

Hierarchy (outermost to innermost):

    EcosystemSpec
     ├─ environment         terrains, fields (continuous layers), generator, environment agents
     ├─ agent_types         brains, bodies (energy, habitat, reproduction), initial population
     ├─ relationships       type-level rules between agent types / fields (eats, affinity, ...)
     ├─ systems             aggregate rules run every tick (growth, metabolism, economy, ...)
     └─ perturbations       which external inputs a user may inject
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TerrainSpec(BaseModel):
    glyph: str = "."
    color: str = "#888888"
    passable: bool = True
    move_cost: float = Field(1.0, ge=0.1)
    capacity: float = Field(0.0, ge=0.0, le=1.0)  # carrying capacity of plant-like fields


class FieldSpec(BaseModel):
    name: str
    max: float = 1.0
    init: float = 0.0
    init_fraction_of_capacity: float | None = None
    color: str = "#3fa34d"


class Component(BaseModel):
    """A reference to a registered system / environment agent plus its parameters."""

    kind: str
    name: str | None = None
    phase: Literal["pre", "post"] = "post"  # only meaningful for systems
    params: dict[str, Any] = Field(default_factory=dict)


class GeneratorSpec(BaseModel):
    kind: str = "noise_terrain"
    params: dict[str, Any] = Field(default_factory=dict)


class EnvironmentSpec(BaseModel):
    width: int = Field(48, ge=4, le=200)
    height: int = Field(32, ge=4, le=200)
    terrains: dict[str, TerrainSpec]
    fields: list[FieldSpec] = Field(default_factory=list)
    generator: GeneratorSpec = Field(default_factory=GeneratorSpec)
    agents: list[Component] = Field(default_factory=list)  # environment agents


class ReproductionSpec(BaseModel):
    threshold: float
    cost: float
    offspring_energy: float
    chance: float = Field(0.05, ge=0, le=1)
    min_age: int = 0
    max_local: int = 6
    radius: float = 3.0


class InitialSpec(BaseModel):
    count: int = Field(0, ge=0, le=2000)
    terrains: list[str] | None = None
    energy: float | None = None


class AgentTypeSpec(BaseModel):
    name: str
    glyph: str = "?"
    color: str = "#ffffff"
    brain: str = "wander"
    brain_params: dict[str, Any] = Field(default_factory=dict)
    max_energy: float = 10.0
    metabolism: float = 0.0
    lifespan: int | None = None
    habitat: list[str] | None = None
    exclusive: bool = False  # at most one such agent per cell
    max_population: int = 400
    reproduce: ReproductionSpec | None = None
    initial: InitialSpec = Field(default_factory=InitialSpec)
    attrs: dict[str, Any] = Field(default_factory=dict)
    attr_choices: dict[str, list[Any]] = Field(default_factory=dict)  # sampled per agent at spawn
    tier: Literal["rule", "llm"] = "rule"  # cost tier, shown in the UI


class RelationshipSpec(BaseModel):
    source: str
    kind: str  # "eats", "affinity", or any kind a brain/action understands
    target: str  # agent type name, or "field:<name>"
    params: dict[str, Any] = Field(default_factory=dict)


class EcosystemSpec(BaseModel):
    name: str
    description: str = ""
    seed: int = 1
    plugins: list[str] = Field(default_factory=list)
    environment: EnvironmentSpec
    agent_types: list[AgentTypeSpec] = Field(default_factory=list)
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    systems: list[Component] = Field(default_factory=list)
    perturbations: list[str] = Field(default_factory=list)
    narrate_every: int = Field(0, ge=0)

    @model_validator(mode="after")
    def _check_references(self) -> EcosystemSpec:
        terrains = set(self.environment.terrains)
        if not terrains:
            raise ValueError("environment.terrains must define at least one terrain")
        types = [t.name for t in self.agent_types]
        if len(set(types)) != len(types):
            raise ValueError("agent type names must be unique")
        fields = {f.name for f in self.environment.fields}
        for t in self.agent_types:
            for tn in (t.habitat or []) + (t.initial.terrains or []):
                if tn not in terrains:
                    raise ValueError(f"agent type {t.name!r} references unknown terrain {tn!r}")
        for r in self.relationships:
            if r.source not in types:
                raise ValueError(f"relationship source {r.source!r} is not an agent type")
            if r.target.startswith("field:"):
                if r.target[6:] not in fields:
                    raise ValueError(f"relationship target {r.target!r} is not a declared field")
            elif r.target not in types:
                raise ValueError(f"relationship target {r.target!r} is not an agent type")
        total = sum(t.initial.count for t in self.agent_types)
        if total > 5000:
            raise ValueError("initial population above 5000 is not supported")
        if self.environment.width * self.environment.height > 20000:
            raise ValueError("world larger than 20000 cells is not supported")
        return self
