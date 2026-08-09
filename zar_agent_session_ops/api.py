from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Annotated, Literal

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException
from fastapi.responses import Response

from . import __version__
from .core import (
    DEFAULT_CONFIG,
    DEFAULT_CLAUDE_SOURCE,
    DEFAULT_DATABASE,
    DEFAULT_SOURCE,
    Policy,
    Session,
    active_blocked_dismissals,
    archive_recoveries,
    archive_session_reversible,
    blocked_candidates,
    blocked_report,
    dismiss_blocked_candidate,
    find_session,
    find_session_by_key,
    load_policy,
    load_sessions,
    markdown_report,
    policy_candidates,
    restore_archived_session,
    restore_blocked_candidate,
    scan_claude,
    scan_codex,
    sync_sessions,
    session_key,
    weekly_report,
)
from .github import session_github_references


LOGGER = logging.getLogger(__name__)


def _session_data(session: Session) -> dict[str, object]:
    return {
        "record_key": session_key(session),
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
        "usage": {
            "observed_at": session.usage.observed_at,
            "input_tokens": session.usage.input_tokens,
            "cached_input_tokens": session.usage.cached_input_tokens,
            "output_tokens": session.usage.output_tokens,
            "reasoning_output_tokens": session.usage.reasoning_output_tokens,
            "total_tokens": session.usage.total_tokens,
            "model_context_window": session.usage.model_context_window,
            "rate_limit_used_percent": session.usage.rate_limit_used_percent,
            "rate_limit_window_minutes": session.usage.rate_limit_window_minutes,
            "rate_limit_resets_at": session.usage.rate_limit_resets_at,
        }
        if session.usage
        else None,
    }


def create_app(
    database: Path = DEFAULT_DATABASE,
    config: Path = DEFAULT_CONFIG,
    source: Path = DEFAULT_SOURCE,
    claude_source: Path = DEFAULT_CLAUDE_SOURCE,
) -> FastAPI:
    app = FastAPI(title="Zar Agent Session Ops", version=__version__)
    refresh_lock = Lock()
    refresh_state: dict[str, object] = {
        "status": "idle",
        "count": None,
        "updated": None,
        "reused": None,
        "duration_seconds": None,
        "started_at": None,
        "finished_at": None,
        "error": None,
    }

    def archive_candidate(record_key: str) -> tuple[Session, Policy]:
        policy = load_policy(config)
        try:
            session = find_session_by_key(database, record_key)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        eligible = {
            session_key(candidate)
            for candidate in policy_candidates(load_sessions(database), policy)
        }
        if record_key not in eligible:
            raise HTTPException(
                status_code=409,
                detail="Session no longer matches the retention policy",
            )
        if session.agent != "codex" or session.source_entry:
            raise HTTPException(
                status_code=409,
                detail="Only direct Codex session files can be archived from the dashboard",
            )
        return session, policy

    def blocked_state() -> tuple[Policy, list[Session], list[tuple[Session, datetime]]]:
        policy = load_policy(config)
        candidates = blocked_candidates(load_sessions(database), policy)
        dismissals = active_blocked_dismissals(database, candidates)
        visible = [
            session for session in candidates if session_key(session) not in dismissals
        ]
        dismissed = [
            (session, dismissals[session_key(session)])
            for session in candidates
            if session_key(session) in dismissals
        ]
        return policy, visible, dismissed

    def blocked_candidate(record_key: str) -> Session:
        policy = load_policy(config)
        try:
            session = find_session_by_key(database, record_key)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        eligible = {
            session_key(candidate)
            for candidate in blocked_candidates(load_sessions(database), policy)
        }
        if record_key not in eligible:
            raise HTTPException(
                status_code=409,
                detail="Session no longer matches the blocked-session heuristic",
            )
        return session

    # ponytail: process-local state is enough for the single-worker local API.
    def run_refresh() -> None:
        started = perf_counter()
        try:
            known = load_sessions(database)
            items = scan_codex(source, known)
            sync_sessions(database, items)
            claude_items = scan_claude(claude_source)
            sync_sessions(database, claude_items, agent="claude")
        except Exception:
            LOGGER.exception("Session refresh failed")
            with refresh_lock:
                refresh_state.update(
                    status="failed",
                    duration_seconds=round(perf_counter() - started, 2),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error="refresh failed; check API logs",
                )
        else:
            refreshed = items + claude_items
            known_by_record = {
                (item.agent, item.session_id, str(item.path), item.source_entry): item
                for item in known
                if item.agent in {"codex", "claude"}
            }
            refreshed_by_record = {
                (item.agent, item.session_id, str(item.path), item.source_entry): item
                for item in refreshed
            }
            reused = sum(
                known_by_record.get(record) == item
                for record, item in refreshed_by_record.items()
            )
            removed = len(known_by_record.keys() - refreshed_by_record.keys())
            with refresh_lock:
                refresh_state.update(
                    status="completed",
                    count=len(refreshed),
                    updated=len(refreshed) - reused + removed,
                    reused=reused,
                    duration_seconds=round(perf_counter() - started, 2),
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
                    updated=None,
                    reused=None,
                    duration_seconds=None,
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
        policy, items, dismissed = blocked_state()
        return {
            "count": len(items),
            "threshold_hours": policy.blocked_after_hours,
            "sessions": [_session_data(item) for item in items],
            "dismissed_count": len(dismissed),
            "dismissed": [
                {**_session_data(item), "dismissed_at": dismissed_at}
                for item, dismissed_at in dismissed
            ],
        }

    @app.post("/api/sessions/{record_key}/blocked-dismissal")
    def dismiss_blocked(
        record_key: str,
        confirmation: Annotated[Literal["NOT_BLOCKED"], Body(embed=True)],
    ) -> dict[str, object]:
        session = blocked_candidate(record_key)
        dismissed_at = dismiss_blocked_candidate(database, session)
        return {
            "record_key": record_key,
            "session_id": session.session_id,
            "dismissed_at": dismissed_at,
            "reactivates_on_activity": True,
        }

    @app.post("/api/blocked-dismissals/{record_key}/restore")
    def restore_blocked(record_key: str) -> dict[str, object]:
        if not restore_blocked_candidate(database, record_key):
            raise HTTPException(status_code=404, detail="Blocked dismissal not found")
        return {"record_key": record_key, "restored": True}

    @app.get("/api/retention")
    def retention() -> dict[str, object]:
        policy = load_policy(config)
        items = policy_candidates(load_sessions(database), policy)
        return {
            "count": len(items),
            "archive_after_days": policy.archive_after_days,
            "sessions": [_session_data(item) for item in items],
        }

    @app.get("/api/archives")
    def archives() -> dict[str, object]:
        items = archive_recoveries(load_policy(config).archive_dir)
        return {"count": len(items), "archives": items}

    @app.get("/api/sessions/{record_key}/archive")
    def archive_preview(record_key: str) -> dict[str, object]:
        session, policy = archive_candidate(record_key)
        try:
            source_path, destination, _ = archive_session_reversible(
                database, session, policy.archive_dir
            )
        except (FileNotFoundError, FileExistsError, OSError) as error:
            raise HTTPException(
                status_code=409,
                detail="Archive preview is unavailable; refresh and try again",
            ) from error
        return {
            "record_key": record_key,
            "session_id": session.session_id,
            "title": session.title,
            "source_name": source_path.name,
            "destination_name": destination.name,
            "size_bytes": session.size_bytes,
            "archive_after_days": policy.archive_after_days,
            "confirmation": "ARCHIVE",
        }

    @app.post("/api/sessions/{record_key}/archive")
    def archive(
        record_key: str,
        confirmation: Annotated[Literal["ARCHIVE"], Body(embed=True)],
    ) -> dict[str, object]:
        session, policy = archive_candidate(record_key)
        try:
            _, destination, _ = archive_session_reversible(
                database, session, policy.archive_dir, apply=True
            )
        except (FileNotFoundError, FileExistsError, OSError) as error:
            raise HTTPException(
                status_code=409,
                detail="Archive failed; refresh and verify the configured destination",
            ) from error
        return {
            "record_key": record_key,
            "session_id": session.session_id,
            "title": session.title,
            "destination_name": destination.name,
            "recovery_available": True,
        }

    @app.post("/api/archives/{record_key}/restore")
    def restore(record_key: str) -> dict[str, object]:
        policy = load_policy(config)
        try:
            restore_archived_session(record_key, policy.archive_dir)
            known = load_sessions(database)
            sync_sessions(database, scan_codex(source, known))
            session = find_session_by_key(database, record_key)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (FileNotFoundError, FileExistsError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=409,
                detail="Restore failed; verify the archived file and original destination",
            ) from error
        return {
            "record_key": record_key,
            "session_id": session.session_id,
            "restored": True,
            "session": _session_data(session),
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
            policy, visible, _ = blocked_state()
            content = blocked_report(visible, policy)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'inline; filename="{report_name}.md"'
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
    Path(os.environ.get("ZAR_CLAUDE_SOURCE", DEFAULT_CLAUDE_SOURCE)),
)
