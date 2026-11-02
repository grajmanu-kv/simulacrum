"""Provider protocol and request type. Only the *intent* layer ever goes through a provider."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMRequest:
    tick: int
    key: str  # unique within a tick, e.g. "12:decide"
    system: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)  # structured form, used by the stub


class LLMProvider(Protocol):
    name: str

    def complete(self, req: LLMRequest) -> str: ...


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a model response; None if there isn't a valid one."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
