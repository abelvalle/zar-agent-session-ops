from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import Response

from . import __version__
from .core import (
    DEFAULT_CONFIG,
    DEFAULT_DATABASE,
    DEFAULT_SOURCE,
    Session,
    blocked_candidates,
    blocked_report,
    find_session,
    load_policy,
    load_sessions,
    markdown_report,
    scan_codex,
    sync_sessions,
    weekly_report,
)
from .github import session_github_references


LOGGER = logging.getLogger(__name__)


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
    database: Path = DEFAULT_DATABASE,
    config: Path = DEFAULT_CONFIG,
    source: Path = DEFAULT_SOURCE,
) -> FastAPI:
    app = FastAPI(title="Zar Agent Session Ops", version=__version__)
    refresh_lock = Lock()
    refresh_state: dict[str, object] = {
        "status": "idle",
        "count": None,
        "started_at": None,
        "finished_at": None,
        "error": None,
    }

    # ponytail: process-local state is enough for the single-worker local API.
    def run_refresh() -> None:
        try:
            items = scan_codex(source)
            sync_sessions(database, items)
        except Exception:
            LOGGER.exception("Session refresh failed")
            with refresh_lock:
                refresh_state.update(
                    status="failed",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error="refresh failed; check API logs",
                )
        else:
            with refresh_lock:
                refresh_state.update(
                    status="completed",
                    count=len(items),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )

    @app.get("/health", include_in_schema=False)
    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/refresh")
    def refresh_status() -> dict[str, object]:
        with refresh_lock:
            return dict(refresh_state)

    @app.post("/api/refresh", status_code=202)
    def refresh(background_tasks: BackgroundTasks) -> dict[str, object]:
        with refresh_lock:
            if refresh_state["status"] != "running":
                refresh_state.update(
                    status="running",
                    count=None,
                    started_at=datetime.now(timezone.utc).isoformat(),
                    finished_at=None,
                    error=None,
                )
                background_tasks.add_task(run_refresh)
            return dict(refresh_state)

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

    @app.get("/api/reports/{report_name}", response_class=Response)
    def report(
        report_name: Literal["sessions", "weekly", "blocked"],
    ) -> Response:
        items = load_sessions(database)
        if report_name == "sessions":
            content = markdown_report(items, 7)
        elif report_name == "weekly":
            content = weekly_report(items)
        else:
            content = blocked_report(items, load_policy(config))
        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{report_name}.md"'
            },
        )

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
    Path(os.environ.get("ZAR_SESSION_SOURCE", DEFAULT_SOURCE)),
)
