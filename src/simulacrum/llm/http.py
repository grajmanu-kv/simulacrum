"""Shared behaviour of providers that call a hosted model over HTTPS.

Each subclass only says how to build the request and how to read the reply. The base class owns what must be the
same for every provider: a per-session call budget, a single deterministic fallback (the offline stub), and
log lines that never contain the request URL, headers or prompt (they may carry credentials or user content).
The fallback answer is recorded like any other response, so a run that used it still replays bit-for-bit.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from simulacrum.llm.base import LLMRequest
from simulacrum.llm.stub import StubProvider

log = logging.getLogger(__name__)


class HttpJsonProvider:
    name = "http"

    def __init__(self, max_calls: int = 400, timeout: float = 30.0):
        self.max_calls = max_calls
        self.timeout = timeout
        self.calls = 0
        self._fallback = StubProvider()

    def _build(self, req: LLMRequest) -> urllib.request.Request:
        raise NotImplementedError

    def _extract(self, data: dict[str, Any]) -> str:
        raise NotImplementedError

    def complete(self, req: LLMRequest) -> str:
        if self.calls >= self.max_calls:
            return self._fallback.complete(req)
        self.calls += 1
        try:
            with urllib.request.urlopen(self._build(req), timeout=self.timeout) as resp:  # noqa: S310 (fixed https URL)
                data = json.load(resp)
            return self._extract(data)
        except Exception as e:
            detail = f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else type(e).__name__
            if not isinstance(e, urllib.error.URLError) and str(e):
                detail += f": {e}"
            log.warning(
                "%s call failed (%s); using offline fallback for tick=%s key=%s", self.name, detail, req.tick, req.key
            )
            return self._fallback.complete(req)