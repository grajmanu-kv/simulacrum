"""Provider selection by name."""

from __future__ import annotations

from simulacrum.config import Settings
from simulacrum.errors import ProviderConfigError
from simulacrum.llm.anthropic import AnthropicProvider
from simulacrum.llm.base import LLMProvider
from simulacrum.llm.gemini import GeminiProvider
from simulacrum.llm.stub import StubProvider

PROVIDERS = ("stub", "anthropic", "gemini")


def make_provider(name: str, settings: Settings | None = None) -> LLMProvider:
    settings = settings or Settings.from_env()
    if name == "stub":
        return StubProvider()
    if name == "anthropic":
        return AnthropicProvider(settings.anthropic_api_key, settings.llm_model, settings.llm_max_calls)
    if name == "gemini":
        return GeminiProvider(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.llm_max_calls,
            max_output_tokens=settings.gemini_max_output_tokens,
            thinking_level=settings.gemini_thinking_level,
        )
    raise ProviderConfigError(f"unknown llm provider {name!r} (use one of {list(PROVIDERS)})")
