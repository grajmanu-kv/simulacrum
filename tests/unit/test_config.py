from __future__ import annotations

import logging
from pathlib import Path

import pytest

from simulacrum.config import BUNDLED_ECOSYSTEMS, Settings, configure_logging


def test_defaults() -> None:
    s = Settings.from_env({})
    assert s.ecosystems_dir == BUNDLED_ECOSYSTEMS and s.port == 8000 and s.max_sessions == 12
    assert s.anthropic_api_key is None


def test_environment_overrides(tmp_path: Path) -> None:
    s = Settings.from_env(
        {
            "SIMULACRUM_ECOSYSTEMS_DIR": str(tmp_path),
            "SIMULACRUM_PORT": "9001",
            "SIMULACRUM_MAX_STEP": "50",
            "SIMULACRUM_LOG_LEVEL": "debug",
            "SIMULACRUM_MODEL": "m",
            "ANTHROPIC_API_KEY": "sk-secret",
        }
    )
    assert s.ecosystems_dir == tmp_path.resolve() and s.port == 9001 and s.max_step == 50
    assert s.log_level == "DEBUG" and s.llm_model == "m"


@pytest.mark.parametrize(
    "env", [{"SIMULACRUM_PORT": "abc"}, {"SIMULACRUM_MAX_STEP": "0"}, {"SIMULACRUM_LOG_LEVEL": "loud"}]
)
def test_invalid_values_fail_fast_with_the_variable_name(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="SIMULACRUM_"):
        Settings.from_env(env)


def test_api_key_never_appears_in_repr() -> None:
    s = Settings.from_env({"ANTHROPIC_API_KEY": "sk-secret"})
    assert s.anthropic_api_key == "sk-secret" and "sk-secret" not in repr(s)


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("DEBUG")
    handlers = [h for h in logging.getLogger("simulacrum").handlers if getattr(h, "_simulacrum", False)]
    assert len(handlers) == 1
