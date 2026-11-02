"""Runtime configuration. Leaf module: imports nothing from this package.

All settings come from ``SIMULACRUM_*`` environment variables (12-factor); the CLI may override
them. API keys are read from ``ANTHROPIC_API_KEY`` / ``GEMINI_API_KEY`` and are excluded from ``repr``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

BUNDLED_ECOSYSTEMS = Path(__file__).resolve().parent / "ecosystems"
_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _int(env: Mapping[str, str], name: str, default: int, lo: int = 1) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value < lo:
        raise ValueError(f"{name} must be >= {lo}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    ecosystems_dir: Path = BUNDLED_ECOSYSTEMS
    host: str = "127.0.0.1"
    port: int = 8000
    max_sessions: int = 12
    max_step: int = 200
    llm_max_calls: int = 400
    llm_model: str = "claude-sonnet-5-5"
    log_level: str = "INFO"
    anthropic_api_key: str | None = field(default=None, repr=False)
    gemini_api_key: str | None = field(default=None, repr=False)
    gemini_model: str = "gemini-3.8-flash"
    gemini_max_output_tokens: int = 2048
    gemini_thinking_level: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        level = e.get("SIMULACRUM_LOG_LEVEL", "INFO").upper()
        if level not in _LEVELS:
            raise ValueError(f"SIMULACRUM_LOG_LEVEL must be one of {sorted(_LEVELS)}, got {level!r}")
        return cls(
            ecosystems_dir=Path(e.get("SIMULACRUM_ECOSYSTEMS_DIR") or BUNDLED_ECOSYSTEMS).resolve(),
            host=e.get("SIMULACRUM_HOST", "127.0.0.1"),
            port=_int(e, "SIMULACRUM_PORT", 8000),
            max_sessions=_int(e, "SIMULACRUM_MAX_SESSIONS", 12),
            max_step=_int(e, "SIMULACRUM_MAX_STEP", 200),
            llm_max_calls=_int(e, "SIMULACRUM_LLM_MAX_CALLS", 400, lo=0),
            llm_model=e.get("SIMULACRUM_MODEL", "claude-sonnet-5-5"),
            log_level=level,
            anthropic_api_key=e.get("ANTHROPIC_API_KEY") or None,
            gemini_api_key=e.get("GEMINI_API_KEY") or None,
            gemini_model=e.get("SIMULACRUM_GEMINI_MODEL", "gemini-3.8-flash"),
            gemini_max_output_tokens=_int(e, "SIMULACRUM_GEMINI_MAX_OUTPUT_TOKENS", 2048, lo=64),
            gemini_thinking_level=e.get("SIMULACRUM_GEMINI_THINKING_LEVEL") or None,
        )


def configure_logging(level: str = "INFO") -> None:
    """Idempotent stderr logging for the ``simulacrum`` logger tree (libraries must not configure the root logger)."""
    log = logging.getLogger("simulacrum")
    log.setLevel(level)
    if not any(getattr(h, "_simulacrum", False) for h in log.handlers):
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        h._simulacrum = True  # type: ignore[attr-defined]
        log.addHandler(h)
