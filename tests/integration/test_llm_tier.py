from __future__ import annotations

import json
import urllib.error
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from simulacrum import AnthropicProvider, Engine, GeminiProvider


class Garbage:
    name = "garbage"

    def __init__(self, reply: str) -> None:
        self.reply = reply

    def complete(self, req: Any) -> str:
        return self.reply


@pytest.mark.parametrize(
    "reply", ["no json here", '{"stance": "conquer_the_moon"}', "{broken", '{"stance": "raid", "target": "x"}']
)
def test_garbage_llm_output_never_crashes_the_world(forest: Callable[..., Engine], reply: str) -> None:
    e = forest(7, llm=Garbage(reply))
    e.run(60)
    tribes = [a for a in e.world.alive_agents() if a.type == "tribe"]
    assert tribes and all(a.attrs["stance"] in ("forage", "raid") for a in tribes)


def test_anthropic_provider_falls_back_offline_and_run_still_replays(
    forest: Callable[..., Engine], eco_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    e = forest(7, llm=AnthropicProvider("test-key"))
    e.run(30)  # every call fails; the stub answers and the run still replays
    assert Engine.verify(e.export_log(), base_dir=eco_dir)["ok"]


def test_a_gemini_driven_run_records_and_replays_exactly(
    forest: Callable[..., Engine], eco_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every council decision comes from the (faked) Gemini endpoint, then replays with no network at all."""
    import io

    class Resp(io.BytesIO):
        def __enter__(self) -> Resp:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    stances = iter(["forage", "hunt", "trade", "migrate", "rest"] * 400)

    def fake(http_req: Any, timeout: float | None = None) -> Resp:
        payload = {
            "candidates": [{"content": {"parts": [{"text": json.dumps({"stance": next(stances), "say": "so"})}]}}]
        }
        return Resp(json.dumps(payload).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake)
    e = forest(7, llm=GeminiProvider("test-key"))
    e.run(40)
    log = e.export_log()
    assert log["llm_provider"] == "gemini"
    assert log["llm"]

    def no_network(*a: Any, **k: Any) -> None:
        raise AssertionError("replay must not call any model")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    assert Engine.verify(log, base_dir=eco_dir)["ok"]
