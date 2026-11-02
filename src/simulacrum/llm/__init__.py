"""LLM tier: providers, recording and replay.

Code owns ground truth (grid, resources, RNG, conflict resolution); a provider only supplies
*intent* (faction decisions, narration). Every response is recorded by ``(tick, key)`` so a run
replays exactly without calling any model.
"""

from simulacrum.llm.anthropic import AnthropicProvider
from simulacrum.llm.base import LLMProvider, LLMRequest, parse_json_object
from simulacrum.llm.factory import PROVIDERS, make_provider
from simulacrum.llm.gemini import GeminiProvider
from simulacrum.llm.replay import RecordingProvider, ReplayMismatch, ReplayProvider
from simulacrum.llm.stub import StubProvider, register_stub_responder

__all__ = [
    "PROVIDERS",
    "AnthropicProvider",
    "GeminiProvider",
    "LLMProvider",
    "LLMRequest",
    "RecordingProvider",
    "ReplayMismatch",
    "ReplayProvider",
    "StubProvider",
    "make_provider",
    "parse_json_object",
    "register_stub_responder",
]
