"""Run logs and deterministic replay verification."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from simulacrum.errors import ReplayMismatch

if TYPE_CHECKING:
    from simulacrum.engine.simulator import Engine

LOG_VERSION = 1


def export_log(engine: Engine) -> dict[str, Any]:
    """Everything needed to reproduce a run: spec, external inputs by tick, recorded LLM responses, final hash."""
    return {
        "version": LOG_VERSION,
        "spec": engine.spec.model_dump(),
        "ticks": engine.world.tick,
        "perturbations": engine.perturbation_log,
        "llm": list(engine.provider.records),
        "llm_provider": engine.provider.name,
        "final_hash": engine.world.state_hash(),
    }


def verify_log(log: dict[str, Any], make_engine: Callable[[dict[str, Any]], Engine]) -> dict[str, Any]:
    """Re-run `log` in a fresh engine and compare final state hashes. Divergence is reported, not raised."""
    eng = make_engine(log)
    try:
        eng.run(int(log["ticks"]))
    except ReplayMismatch as e:  # the run diverged and asked for a decision that was never recorded
        return {"ok": False, "expected": log["final_hash"], "got": None, "ticks": eng.world.tick, "error": str(e)}
    got = eng.world.state_hash()
    return {"ok": got == log["final_hash"], "expected": log["final_hash"], "got": got, "ticks": log["ticks"]}
