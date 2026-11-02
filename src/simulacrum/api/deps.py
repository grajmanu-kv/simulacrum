"""FastAPI dependencies: everything a route needs comes from ``app.state``, never from module globals."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from simulacrum.api.sessions import Session, SessionStore
from simulacrum.config import Settings
from simulacrum.repository import EcosystemRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_store(request: Request) -> SessionStore:
    return request.app.state.sessions


def get_repository(request: Request) -> EcosystemRepository:
    return request.app.state.repository


def get_session(sid: str, store: Annotated[SessionStore, Depends(get_store)]) -> Session:
    return store.get(sid)


SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[SessionStore, Depends(get_store)]
RepoDep = Annotated[EcosystemRepository, Depends(get_repository)]
SessionDep = Annotated[Session, Depends(get_session)]
