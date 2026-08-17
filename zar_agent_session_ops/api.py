from __future__ import annotations

import logging
import os
import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Annotated, Literal

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Request
from fastapi.responses import Response

from . import __version__
from .core import (
    DEFAULT_CONFIG,
    DEFAULT_CLAUDE_SOURCE,
    DEFAULT_DATABASE,
    DEFAULT_SOURCE,
    Policy,
    Session,
    TokenUsage,
    active_blocked_dismissals,
    archive_recoveries,
    archive_session_reversible,
    base_session_handoff,
    blocked_candidates,
    blocked_report,
    dismiss_blocked_candidate,
    extract_session_transcript,
    find_session,
    find_session_by_key,
    load_policy,
    load_sessions,
    latest_codex_usage,
    list_ollama_models,
    markdown_report,
    maintenance_history,
    operational_digest_history,
    policy_candidates,
    record_maintenance_preview,
    record_operational_digest,
    restore_archived_session,
    restore_blocked_candidate,
    scan_claude,
    scan_chatgpt_export,
    scan_codex,
    save_policy,
    session_activity,
    sync_sessions,
    summarize_with_ollama,
    weekly_digest,
    session_key,
    weekly_report,
)
from .github import session_github_references


LOGGER = logging.getLogger(__name__)
USAGE_STALE_AFTER_SECONDS = 15 * 60
CHATGPT_UPLOAD_MAX_BYTES = 100 * 1024 * 1024
CHATGPT_EXPANDED_MAX_BYTES = 500 * 1024 * 1024


async def _chatgpt_upload(request: Request) -> tuple[bytes, str]:
    filename = request.headers.get("x-filename", "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".zip", ".json"}:
        raise HTTPException(status_code=422, detail="Upload a ChatGPT ZIP or JSON export")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > CHATGPT_UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail="ChatGPT export exceeds 100 MiB")
        chunks.append(chunk)
    if size == 0:
        raise HTTPException(status_code=422, detail="ChatGPT export is empty")
    return b"".join(chunks), suffix


def _validate_chatgpt_archive(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        return
    with zipfile.ZipFile(path) as archive:
        expanded = sum(
            item.file_size
            for item in archive.infolist()
            if Path(item.filename).name.lower().startswith("conversations")
            and Path(item.filename).suffix.lower() == ".json"
        )
    if expanded > CHATGPT_EXPANDED_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Expanded ChatGPT conversations exceed 500 MiB")


def _usage_data(usage: TokenUsage) -> dict[str, object]:
    return {
        "observed_at": usage.observed_at,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_output_tokens": usage.reasoning_output_tokens,
        "total_tokens": usage.total_tokens,
        "model_context_window": usage.model_context_window,
        "rate_limit_used_percent": usage.rate_limit_used_percent,
        "rate_limit_window_minutes": usage.rate_limit_window_minutes,
        "rate_limit_resets_at": usage.rate_limit_resets_at,
    }


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
        "usage": _usage_data(session.usage)
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
    chatgpt_import_dir = config.parent / "chatgpt-imports"

    def source_inventory() -> dict[str, object]:
        items = load_sessions(database)
        counts = {
            agent: sum(item.agent == agent for item in items)
            for agent in ("codex", "claude", "chatgpt")
        }
        return {
            "sources": [
                {
                    "id": "codex",
                    "label": "Codex",
                    "status": "available" if source.is_dir() else "unavailable",
                    "session_count": counts["codex"],
                    "import_supported": False,
                },
                {
                    "id": "claude",
                    "label": "Claude Code",
                    "status": (
                        "available"
                        if (claude_source / "sessions").is_dir()
                        else "unavailable"
                    ),
                    "session_count": counts["claude"],
                    "import_supported": False,
                },
                {
                    "id": "chatgpt",
                    "label": "ChatGPT",
                    "status": "imported" if counts["chatgpt"] else "awaiting_import",
                    "session_count": counts["chatgpt"],
                    "import_supported": True,
                },
                {
                    "id": "opencode",
                    "label": "OpenCode",
                    "status": "not_configured",
                    "session_count": 0,
                    "import_supported": False,
                },
            ]
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

    @app.get("/api/usage")
    def usage() -> dict[str, object]:
        snapshot = latest_codex_usage(source)
        if snapshot is None:
            return {
                "status": "unavailable",
                "source": "latest_local_codex_event",
                "session_id": None,
                "observed_at": None,
                "age_seconds": None,
                "stale": True,
                "usage": None,
            }
        age_seconds = max(
            0,
            int((datetime.now(timezone.utc) - snapshot.usage.observed_at).total_seconds()),
        )
        return {
            "status": "available",
            "source": "latest_local_codex_event",
            "session_id": snapshot.session_id,
            "observed_at": snapshot.usage.observed_at,
            "age_seconds": age_seconds,
            "stale": age_seconds > USAGE_STALE_AFTER_SECONDS,
            "usage": _usage_data(snapshot.usage),
        }

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

    @app.get("/api/policy")
    def policy() -> dict[str, int]:
        current = load_policy(config)
        return {
            "archive_after_days": current.archive_after_days,
            "blocked_after_hours": current.blocked_after_hours,
        }

    @app.put("/api/policy")
    def update_policy(
        archive_after_days: Annotated[int, Body(embed=True, ge=1, le=3_650)],
        blocked_after_hours: Annotated[int, Body(embed=True, ge=1, le=8_760)],
    ) -> dict[str, int]:
        try:
            saved = save_policy(config, archive_after_days, blocked_after_hours)
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "archive_after_days": saved.archive_after_days,
            "blocked_after_hours": saved.blocked_after_hours,
        }

    @app.get("/api/maintenance/history")
    def maintenance_runs() -> dict[str, object]:
        runs = maintenance_history(database)
        return {"count": len(runs), "runs": runs}

    @app.get("/api/sources")
    def sources() -> dict[str, object]:
        return source_inventory()

    @app.get("/api/ollama")
    def ollama() -> dict[str, object]:
        try:
            models = list_ollama_models()
        except RuntimeError:
            return {"status": "unavailable", "models": [], "local_only": True}
        return {
            "status": "ready" if models else "no_models",
            "models": models,
            "local_only": True,
        }

    @app.get("/api/digests/weekly")
    def weekly_digests() -> dict[str, object]:
        items = operational_digest_history(database)
        return {"count": len(items), "digests": items}

    @app.post("/api/digests/weekly")
    def generate_weekly_digest(
        model: Annotated[str, Body(embed=True, min_length=1, max_length=200)],
    ) -> dict[str, object]:
        try:
            models = list_ollama_models()
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="Local Ollama is unavailable") from error
        if not models:
            raise HTTPException(status_code=409, detail="No local Ollama models are installed")
        if model not in models:
            raise HTTPException(status_code=409, detail="Selected Ollama model is not installed")
        try:
            markdown = weekly_digest(load_sessions(database), model)
            return record_operational_digest(database, model, markdown)
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @app.post("/api/imports/chatgpt/preview")
    async def preview_chatgpt_import(request: Request) -> dict[str, object]:
        payload, suffix = await _chatgpt_upload(request)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"upload{suffix}"
                path.write_bytes(payload)
                _validate_chatgpt_archive(path)
                sessions = scan_chatgpt_export(path)
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            raise HTTPException(status_code=422, detail="Invalid ChatGPT export") from error
        return {
            "conversation_count": len(sessions),
            "conversations": [
                {
                    "id": item.session_id,
                    "title": item.title,
                    "last_activity_at": item.last_activity_at,
                    "event_count": item.event_count,
                }
                for item in sessions[:10]
            ],
            "shown_count": min(10, len(sessions)),
            "confirmation": "IMPORT_CHATGPT",
        }

    @app.post("/api/imports/chatgpt")
    async def import_chatgpt(request: Request) -> dict[str, object]:
        if request.headers.get("x-confirmation") != "IMPORT_CHATGPT":
            raise HTTPException(status_code=422, detail="IMPORT_CHATGPT confirmation required")
        payload, suffix = await _chatgpt_upload(request)
        digest = hashlib.sha256(payload).hexdigest()
        chatgpt_import_dir.mkdir(parents=True, exist_ok=True)
        path = chatgpt_import_dir / f"{digest}{suffix}"
        created = not path.exists()
        try:
            if created:
                temporary = path.with_suffix(path.suffix + ".tmp")
                temporary.write_bytes(payload)
                temporary.replace(path)
            _validate_chatgpt_archive(path)
            imported = scan_chatgpt_export(path)
            all_sessions: dict[str, Session] = {}
            for stored_export in sorted(chatgpt_import_dir.iterdir()):
                if stored_export.suffix.lower() not in {".zip", ".json"}:
                    continue
                for session in scan_chatgpt_export(stored_export):
                    all_sessions[session.session_id] = session
            sync_sessions(database, list(all_sessions.values()), agent="chatgpt")
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            if created:
                path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Invalid ChatGPT export") from error
        return {
            "imported_count": len(imported),
            "total_chatgpt_sessions": len(all_sessions),
            "stored_locally": True,
        }

    @app.post("/api/maintenance/preview")
    def maintenance_preview() -> dict[str, object]:
        current = load_policy(config)
        items = load_sessions(database)
        archive_items = policy_candidates(items, current)
        blocked_items = blocked_candidates(items, current)
        dismissals = active_blocked_dismissals(database, blocked_items)
        visible_blocked = [
            item for item in blocked_items if session_key(item) not in dismissals
        ]
        run = record_maintenance_preview(
            database, current, len(archive_items), len(visible_blocked)
        )
        return {
            **run,
            "archive_candidates": [_session_data(item) for item in archive_items],
            "blocked_candidates": [_session_data(item) for item in visible_blocked],
        }

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

    @app.get("/api/sessions/{record_key}/handoff", response_class=Response)
    def handoff(record_key: str) -> Response:
        try:
            session = find_session_by_key(database, record_key)
            transcript = extract_session_transcript(session)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail="Handoff source is unavailable; refresh the inventory and try again",
            ) from error
        return Response(
            content=base_session_handoff(session, transcript),
            media_type="text/markdown",
            headers={
                "Content-Disposition": 'inline; filename="session-handoff.md"'
            },
        )

    @app.get("/api/sessions/{record_key}/activity")
    def activity(record_key: str) -> dict[str, object]:
        try:
            session = find_session_by_key(database, record_key)
            transcript = extract_session_transcript(session)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail="Activity source is unavailable; refresh the inventory and try again",
            ) from error
        return session_activity(session, transcript)

    @app.post("/api/sessions/{record_key}/summary")
    def session_summary(
        record_key: str,
        model: Annotated[str, Body(embed=True, min_length=1, max_length=200)],
    ) -> dict[str, object]:
        try:
            models = list_ollama_models()
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="Local Ollama is unavailable") from error
        if not models:
            raise HTTPException(status_code=409, detail="No local Ollama models are installed")
        if model not in models:
            raise HTTPException(status_code=409, detail="Selected Ollama model is not installed")
        try:
            session = find_session_by_key(database, record_key)
            transcript = extract_session_transcript(session)
            markdown = summarize_with_ollama(transcript, model)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (FileNotFoundError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail="Summary source is unavailable; refresh the inventory and try again",
            ) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return {
            "model": model,
            "markdown": markdown,
            "generated_at": datetime.now(timezone.utc),
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
