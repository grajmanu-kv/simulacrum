"""The single-page UI. Assets live in ``simulacrum/web/static`` and are mounted at /static."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "static"
router = APIRouter(include_in_schema=False)


@router.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
