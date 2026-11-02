"""Request/response models. These are the public HTTP contract (see docs/api.md)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    ecosystem: str | None = Field(None, description="File stem inside the ecosystems directory.")
    spec: dict[str, Any] | None = Field(None, description="Inline declarative spec (plugins are rejected).")
    seed: int | None = None
    llm: str = Field("stub", description="'stub' (offline, deterministic), 'anthropic' or 'gemini'.")


class StepRequest(BaseModel):
    n: int = Field(1, ge=1, description="Ticks to advance; capped by SIMULACRUM_MAX_STEP.")


class PerturbRequest(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class EcosystemInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    seed: int = 1
    plugins: list[str] = Field(default_factory=list)


class Components(BaseModel):
    brains: list[str]
    actions: list[str]
    systems: list[str]
    environment_agents: list[str]
    generators: list[str]
    perturbations: list[str]


class Health(BaseModel):
    status: str


class Readiness(BaseModel):
    status: str
    ecosystems_dir: bool
    sessions: int
    max_sessions: int


class VersionInfo(BaseModel):
    name: str = "simulacrum"
    version: str
