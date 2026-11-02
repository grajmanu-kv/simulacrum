"""Ecosystem repository: discovers and loads spec files from the operator-controlled directory."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from simulacrum.core.spec import EcosystemSpec
from simulacrum.errors import EcosystemNotFound

log = logging.getLogger(__name__)


def load_spec(path: str | Path) -> tuple[EcosystemSpec, Path]:
    """Read an ecosystem JSON file; returns (spec, directory used to resolve plugin paths)."""
    p = Path(path)
    return EcosystemSpec.model_validate_json(p.read_text()), p.parent


@dataclass(frozen=True)
class EcosystemRepository:
    root: Path

    def exists(self) -> bool:
        return self.root.is_dir()

    def list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self.root.glob("*.json")):
            try:
                raw = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                log.warning("skipping unreadable ecosystem file %s", p.name)
                continue
            out.append(
                {
                    "id": p.stem,
                    "name": raw.get("name", p.stem),
                    "description": raw.get("description", ""),
                    "seed": raw.get("seed", 1),
                    "plugins": raw.get("plugins", []),
                }
            )
        return out

    def load(self, ecosystem_id: str) -> tuple[EcosystemSpec, Path]:
        """Load by id (file stem). Ids that resolve outside the root are treated as not found."""
        path = (self.root / f"{ecosystem_id}.json").resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            raise EcosystemNotFound(f"no ecosystem named {ecosystem_id!r}")
        return load_spec(path)
