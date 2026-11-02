"""Recording and replay wrappers: what makes an LLM-driven run reproducible."""

from __future__ import annotations

from typing import Any

from simulacrum.errors import ReplayMismatch
from simulacrum.llm.base import LLMProvider, LLMRequest


class RecordingProvider:
    def __init__(self, inner: LLMProvider):
        self.inner = inner
        self.name = inner.name
        self.records: list[dict[str, Any]] = []

    def complete(self, req: LLMRequest) -> str:
        text = self.inner.complete(req)
        self.records.append({"tick": req.tick, "key": req.key, "response": text})
        return text


class ReplayProvider:
    name = "replay"

    def __init__(self, records: list[dict[str, Any]]):
        self._by_key = {(r["tick"], r["key"]): r["response"] for r in records}
        self.records = list(records)

    def complete(self, req: LLMRequest) -> str:
        try:
            return self._by_key[(req.tick, req.key)]
        except KeyError:
            raise ReplayMismatch(f"no recorded LLM response for tick={req.tick} key={req.key!r}") from None
