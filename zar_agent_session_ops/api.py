from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from . import __version__
from .core import (
    DEFAULT_CONFIG,
    DEFAULT_DATABASE,
    Session,
    blocked_candidates,
    find_session,
    load_policy,
    load_sessions,
)
from .github import session_github_references


def _session_data(session: Session) -> dict[str, object]:
    return {
        "id": session.session_id,
        "agent": session.agent,
        "title": session.title,
        "status": session.status,
        "repository": session.repository,
        "started_at": session.started_at,
        "last_activity_at": session.last_activity_at,
        "size_bytes": session.size_bytes,
        "event_count": session.event_count,
        "origin": session.origin,
        "thread_source": session.thread_source,
        "last_event_type": session.last_event_type,
    }


def create_app(
    database: Path = DEFAULT_DATABASE, config: Path = DEFAULT_CONFIG
) -> FastAPI:
    app = FastAPI(title="Zar Agent Session Ops", version=__version__)

    @app.get("/health", include_in_schema=False)
    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/sessions", include_in_schema=False)
    @app.get("/api/sessions")
    def sessions(
        agent: str | None = None, status: str | None = None
    ) -> dict[str, object]:
        items = load_sessions(database)
        if agent:
            items = [item for item in items if item.agent == agent]
        if status:
            items = [item for item in items if item.status == status]
        return {
            "count": len(items),
            "sessions": [_session_data(item) for item in items],
        }

    @app.get("/blocked", include_in_schema=False)
    @app.get("/api/blocked")
    def blocked() -> dict[str, object]:
        policy = load_policy(config)
        items = blocked_candidates(load_sessions(database), policy)
        return {
            "count": len(items),
            "threshold_hours": policy.blocked_after_hours,
            "sessions": [_session_data(item) for item in items],
        }

    @app.get("/api/sessions/{session_id}/github")
    def github(session_id: str) -> dict[str, object]:
        try:
            session = find_session(database, session_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        try:
            references = session_github_references(session)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "session_id": session.session_id,
            "count": len(references),
            "references": references,
        }

    return app


app = create_app(
    Path(os.environ.get("ZAR_SESSION_DB", DEFAULT_DATABASE)),
    Path(os.environ.get("ZAR_SESSION_CONFIG", DEFAULT_CONFIG)),
)
