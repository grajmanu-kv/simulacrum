"""Application factory.

    uvicorn --factory simulacrum.api.app:create_app      # settings from SIMULACRUM_* env vars
    create_app(Settings(...))                            # explicit, e.g. in tests

Run a single worker: sessions live in process memory.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from simulacrum._version import __version__
from simulacrum.api.routers import catalog, health, sessions, ui
from simulacrum.api.routers.ui import STATIC_DIR
from simulacrum.api.sessions import SessionStore
from simulacrum.config import Settings, configure_logging
from simulacrum.engine import discover_entry_point_plugins
from simulacrum.errors import EcosystemNotFound, SessionNotFound, SimulacrumError
from simulacrum.repository import EcosystemRepository

log = logging.getLogger(__name__)
_RID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    discover_entry_point_plugins()

    app = FastAPI(
        title="Simulacrum", version=__version__, description="Declarative, extensible, replayable world simulation."
    )
    app.state.settings = settings
    app.state.sessions = SessionStore(settings.max_sessions)
    app.state.repository = EcosystemRepository(settings.ecosystems_dir)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        supplied = request.headers.get("x-request-id", "")
        rid = supplied if _RID.match(supplied) else uuid.uuid4().hex[:12]  # never log unvalidated client text
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        response.headers["x-content-type-options"] = "nosniff"
        if not request.url.path.startswith("/static"):
            log.info(
                "%s %s -> %s %.1fms rid=%s",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - start) * 1000,
                rid,
            )
        return response

    @app.exception_handler(SessionNotFound)
    @app.exception_handler(EcosystemNotFound)
    async def not_found(_: Request, exc: SimulacrumError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(SimulacrumError)
    async def domain_error(_: Request, exc: SimulacrumError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    for r in (ui.router, health.router, catalog.router, sessions.router):
        app.include_router(r)
    return app
