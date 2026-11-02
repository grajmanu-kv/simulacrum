from __future__ import annotations

import pytest
from pydantic import ValidationError

from simulacrum import EcosystemSpec

BASE = {"name": "bad", "environment": {"terrains": {"a": {}}}, "agent_types": [{"name": "x"}]}


def test_relationship_must_reference_declared_types() -> None:
    with pytest.raises(ValidationError):
        EcosystemSpec.model_validate({**BASE, "relationships": [{"source": "x", "kind": "eats", "target": "ghost"}]})


def test_habitat_must_reference_declared_terrains() -> None:
    with pytest.raises(ValidationError):
        EcosystemSpec.model_validate({**BASE, "agent_types": [{"name": "x", "habitat": ["lava"]}]})


def test_world_size_is_capped() -> None:
    with pytest.raises(ValidationError):
        EcosystemSpec.model_validate({**BASE, "environment": {"width": 200, "height": 200, "terrains": {"a": {}}}})


def test_minimal_spec_is_valid() -> None:
    assert EcosystemSpec.model_validate(BASE).name == "bad"
