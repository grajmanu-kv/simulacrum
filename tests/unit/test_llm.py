from __future__ import annotations

import urllib.error
from typing import Any

import pytest

from simulacrum import AnthropicProvider, Settings, StubProvider, make_provider
from simulacrum.errors import ProviderConfigError, ReplayMismatch
from simulacrum.llm import LLMRequest, RecordingProvider, ReplayProvider, parse_json_object, register_stub_responder


def req(tick: int = 1, key: str = "1:decide") -> LLMRequest:
    ctx = {
        "kind": "decision",
        "pop": 10,
        "food": 5.0,
        "trait": "peaceful",
        "neighbors": [],
        "local_plants": 0.5,
        "local_prey": 0,
    }
    return LLMRequest(tick, key, "sys", "prompt", ctx)


def test_parse_json_object() -> None:
    assert parse_json_object('Sure! {"stance": "trade"} thanks') == {"stance": "trade"}
    assert parse_json_object("[1,2]") is None and parse_json_object("") is None
    assert parse_json_object("{broken") is None


def test_stub_is_deterministic_per_tick_and_key() -> None:
    s = StubProvider()
    assert s.complete(req(3, "a")) == s.complete(req(3, "a"))


def test_recording_then_replay_returns_same_text_and_rejects_unknown_requests() -> None:
    rec = RecordingProvider(StubProvider())
    text = rec.complete(req(2, "k"))
    replay = ReplayProvider(rec.records)
    assert replay.complete(req(2, "k")) == text
    with pytest.raises(ReplayMismatch):
        replay.complete(req(99, "never-recorded"))


def test_make_provider_rejects_unknown_name_and_missing_key() -> None:
    with pytest.raises(ProviderConfigError, match="unknown llm provider"):
        make_provider("gpt-whatever", Settings())
    with pytest.raises(ProviderConfigError, match="ANTHROPIC_API_KEY"):
        make_provider("anthropic", Settings(anthropic_api_key=None))
    assert make_provider("anthropic", Settings(anthropic_api_key="k")).name == "anthropic"


def test_anthropic_provider_budget_and_failure_both_fall_back_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def boom(*a: Any, **k: Any) -> None:
        calls["n"] += 1
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    p = AnthropicProvider("k", max_calls=2)
    outs = [p.complete(req(t, f"{t}:decide")) for t in range(5)]
    assert calls["n"] == 2  # budget respected: calls 3-5 never touched the network
    assert all(parse_json_object(o) for o in outs)  # every reply is still a valid stub decision


def test_plugins_can_register_an_offline_answer_for_their_own_request_kind() -> None:
    @register_stub_responder("unit_test_kind")
    def answer(ctx: dict[str, Any], u: float) -> dict[str, Any]:
        return {"echo": ctx["n"], "u_in_range": 0 <= u < 1}

    out = parse_json_object(StubProvider().complete(LLMRequest(4, "k", "s", "p", {"kind": "unit_test_kind", "n": 7})))
    assert out == {"echo": 7, "u_in_range": True}


def test_requests_of_unregistered_kinds_still_get_the_faction_heuristic() -> None:
    out = parse_json_object(StubProvider().complete(req()))
    assert out is not None
    assert out["stance"] in ("forage", "hunt", "trade", "raid", "migrate", "found", "rest")
