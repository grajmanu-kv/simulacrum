from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simulacrum import Engine, Settings, load_spec
from simulacrum.api import create_app
from simulacrum.config import BUNDLED_ECOSYSTEMS


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in Path(str(item.fspath)).parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def eco_dir() -> Path:
    return BUNDLED_ECOSYSTEMS


@pytest.fixture
def forest(eco_dir: Path) -> Callable[..., Engine]:
    def make(seed: int | None = None, llm: Any = None) -> Engine:
        spec, base = load_spec(eco_dir / "forest.json")
        if seed is not None:
            spec.seed = seed
        return Engine(spec, base_dir=base, llm=llm)

    return make


@pytest.fixture
def junction(eco_dir: Path) -> Callable[..., Engine]:
    def make(**brain_params: Any) -> Engine:
        spec, base = load_spec(eco_dir / "junction.json")
        spec.agent_types[0].brain_params.update(brain_params)
        return Engine(spec, base_dir=base)

    return make


@pytest.fixture
def settings(eco_dir: Path) -> Settings:
    return Settings(ecosystems_dir=eco_dir)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))
