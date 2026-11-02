"""Google Gemini provider, via the ``generateContent`` REST endpoint (stdlib HTTP).

Contract used (https://ai.google.dev/api/generate-content, checked 2026-11-02):

    POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    header  x-goog-api-key: <key>            (never put the key in the URL: URLs end up in logs)
    body    {"systemInstruction": {"parts": [{"text": ...}]},
             "contents": [{"role": "user", "parts": [{"text": ...}]}],
             "generationConfig": {"maxOutputTokens": N [, "thinkingConfig": {"thinkingLevel": L}]}}
    reply   {"candidates": [{"content": {"parts": [{"text": ...}]}, "finishReason": ...}],
             "promptFeedback": {"blockReason": ...}}

Thinking tokens count against ``maxOutputTokens``; a small cap on a thinking model can return an empty reply with
``finishReason: MAX_TOKENS``. The default cap is therefore generous, and an empty or blocked reply is treated as a
failure (offline fallback, logged) instead of being handed to the world as if it were a decision.

Google marks ``generateContent`` as the "legacy" API and points to the Interactions API as its successor; this
provider does not use the latter.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from simulacrum.errors import ProviderConfigError, ProviderReplyError
from simulacrum.llm.base import LLMRequest
from simulacrum.llm.http import HttpJsonProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.8-flash"
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


class GeminiProvider(HttpJsonProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_MODEL,
        max_calls: int = 400,
        timeout: float = 30.0,
        max_output_tokens: int = 2048,
        thinking_level: str | None = None,
    ):
        if not api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not set on the server; use the offline provider (stub) instead"
            )
        if not _MODEL.match(model):
            raise ProviderConfigError(f"invalid Gemini model id {model!r}")
        super().__init__(max_calls, timeout)
        self._api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.thinking_level = thinking_level or None

    def _build(self, req: LLMRequest) -> urllib.request.Request:
        config: dict[str, Any] = {"maxOutputTokens": self.max_output_tokens}
        if self.thinking_level:
            config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        body = json.dumps(
            {
                "systemInstruction": {"parts": [{"text": req.system}]},
                "contents": [{"role": "user", "parts": [{"text": req.prompt}]}],
                "generationConfig": config,
            }
        ).encode()
        return urllib.request.Request(  # noqa: S310 (https base URL; model id validated by _MODEL)
            f"{BASE_URL}/{self.model}:generateContent",
            data=body,
            method="POST",
            headers={"x-goog-api-key": self._api_key, "content-type": "application/json"},
        )

    def _extract(self, data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise ProviderReplyError(f"no usable candidate ({reason})")
        first = candidates[0]
        parts = (first.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise ProviderReplyError(f"empty reply (finishReason={first.get('finishReason')})")
        return text