"""Anthropic Messages API provider (stdlib HTTP; budget and fallback come from ``HttpJsonProvider``)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from simulacrum.errors import ProviderConfigError
from simulacrum.llm.base import LLMRequest
from simulacrum.llm.http import HttpJsonProvider

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"


class AnthropicProvider(HttpJsonProvider):
    """Falls back to the stub on any error or once `max_calls` is exhausted."""

    name = "anthropic"

    def __init__(self, api_key: str | None, model: str = DEFAULT_MODEL, max_calls: int = 400, timeout: float = 30.0):
        if not api_key:
            raise ProviderConfigError(
                "ANTHROPIC_API_KEY is not set on the server; use the offline provider (stub) instead"
            )
        super().__init__(max_calls, timeout)
        self._api_key = api_key
        self.model = model

    def _build(self, req: LLMRequest) -> urllib.request.Request:
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": 300,
                "system": req.system,
                "messages": [{"role": "user", "content": req.prompt}],
            }
        ).encode()
        return urllib.request.Request(
            API_URL,
            data=body,
            method="POST",
            headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        )

    def _extract(self, data: dict[str, Any]) -> str:
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
