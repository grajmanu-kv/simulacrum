"""Session lifecycle: create a world, step it, inject external inputs, read it back, verify its replay."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from simulacrum.api.deps import RepoDep, SessionDep, SettingsDep, StoreDep
from simulacrum.api.schemas import CreateSessionRequest, PerturbRequest, StepRequest
from simulacrum.core.spec import EcosystemSpec
from simulacrum.engine import Engine
from simulacrum.errors import LimitExceeded, PluginSecurityError, SimulacrumError
from simulacrum.llm import make_provider

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("")
def create_session(req: CreateSessionRequest, repo: RepoDep, store: StoreDep, settings: SettingsDep) -> dict[str, Any]:
    base = None
    try:
        if req.spec is not None:
            if req.spec.get("plugins"):
                raise PluginSecurityError(
                    "inline specs cannot load plugins; put the spec and plugin in the ecosystems directory"
                )
            spec = EcosystemSpec.model_validate(req.spec)
            name = spec.name
        elif req.ecosystem:
            spec, base = repo.load(req.ecosystem)
            name = req.ecosystem
        else:
            raise HTTPException(400, "provide 'ecosystem' or 'spec'")
        if req.seed is not None:
            spec.seed = req.seed
        provider = make_provider(req.llm, settings)
        engine = Engine(spec, base_dir=base, llm=provider, plugin_root=settings.ecosystems_dir)
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json())) from e
    except SimulacrumError:
        raise  # mapped to 400/404 by the app's exception handlers
    except (KeyError, ValueError, PermissionError, ImportError) as e:  # raised by user plugins
        raise HTTPException(400, str(e)) from e
    session = store.add(engine, name)
    log.info("session %s created: %s seed=%s llm=%s", session.id, name, spec.seed, engine.provider.name)
    return {
        "session": session.id,
        "snapshot": engine.snapshot(),
        "catalog": engine.perturbation_catalog(),
        "spec_name": name,
        "description": spec.description,
        "llm": engine.provider.name,
    }


@router.post("/{sid}/step")
def step(session: SessionDep, req: StepRequest, settings: SettingsDep) -> dict[str, Any]:
    if req.n > settings.max_step:
        raise LimitExceeded(f"n must be <= {settings.max_step}")
    with session.lock:
        try:
            session.engine.run(req.n)
        except Exception as e:  # surface plugin errors to the UI instead of a bare 500
            log.exception("session %s failed while stepping", session.id)
            raise HTTPException(500, f"{type(e).__name__}: {e}") from e
        return session.engine.snapshot()


@router.post("/{sid}/perturb")
def perturb(session: SessionDep, req: PerturbRequest) -> dict[str, Any]:
    with session.lock:
        queued = session.engine.perturb(req.name, req.params)
        log.info("session %s: queued %s for tick %s", session.id, req.name, queued["tick"])
        return {"queued": queued, "snapshot": session.engine.snapshot()}


@router.get("/{sid}/state")
def state(session: SessionDep) -> dict[str, Any]:
    with session.lock:
        return session.engine.snapshot()


@router.get("/{sid}/text", response_class=PlainTextResponse)
def text(session: SessionDep, field: str | None = None) -> str:
    with session.lock:
        if field and field not in session.engine.world.fields:
            raise HTTPException(400, f"unknown field {field!r}")
        return session.engine.render_ascii(field)


@router.get("/{sid}/spec")
def spec_of(session: SessionDep) -> dict[str, Any]:
    return session.engine.spec.model_dump()


@router.get("/{sid}/log")
def run_log(session: SessionDep) -> dict[str, Any]:
    with session.lock:
        return session.engine.export_log()


@router.post("/{sid}/verify")
def verify(session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
    """Re-run the session from its log in a fresh engine and compare final state hashes."""
    with session.lock:
        lg = session.engine.export_log()
        base = session.engine.base_dir
    try:
        return Engine.verify(lg, base_dir=base, plugin_root=settings.ecosystems_dir)
    except Exception as e:
        log.exception("session %s replay failed", session.id)
        raise HTTPException(500, f"replay failed: {type(e).__name__}: {e}") from e
