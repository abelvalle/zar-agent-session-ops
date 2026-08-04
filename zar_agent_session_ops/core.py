from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tomllib
import zipfile
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_DATABASE = Path.home() / ".zar-agent-session-ops" / "sessions.db"
DEFAULT_CONFIG = Path.home() / ".zar-agent-session-ops" / "config.toml"
DEFAULT_SOURCE = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


@dataclass(frozen=True)
class Session:
    session_id: str
    agent: str
    path: Path
    repository: str
    started_at: datetime
    last_activity_at: datetime
    size_bytes: int
    event_count: int
    status: str = "active"
    title: str = ""
    origin: str = ""
    thread_source: str = ""
    source_entry: str = ""
    last_event_type: str = ""


@dataclass(frozen=True)
class Policy:
    archive_after_days: int
    archive_dir: Path
    blocked_after_hours: int = 24


@contextmanager
def _connect(database: Path):
    connection = sqlite3.connect(database)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _timestamp(value: object, fallback: datetime) -> datetime:
    if not isinstance(value, str):
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return fallback


def load_session_titles(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    titles: dict[str, str] = {}
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and item.get("id") and item.get("thread_name"):
                titles[str(item["id"])] = str(item["thread_name"])
    return titles


def read_codex_session(
    path: Path, status: str = "active", titles: dict[str, str] | None = None
) -> Session:
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    started = modified
    last_activity: datetime | None = None
    session_id = path.stem
    repository = ""
    origin = ""
    thread_source = ""
    last_event_type = ""
    event_count = 0

    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue

            event_count += 1
            observed_at = _timestamp(item.get("timestamp"), modified)
            if event_count == 1:
                started = observed_at
            last_activity = max(last_activity or observed_at, observed_at)

            if item.get("type") == "event_msg":
                payload = item.get("payload")
                if isinstance(payload, dict) and payload.get("type") in {
                    "task_started",
                    "task_complete",
                    "turn_aborted",
                }:
                    last_event_type = str(payload["type"])

            if item.get("type") == "session_meta":
                payload = item.get("payload") or {}
                if not isinstance(payload, dict):
                    continue
                session_id = payload.get("id") or payload.get("session_id") or session_id
                repository = payload.get("cwd") or repository
                origin = payload.get("originator") or origin
                source = payload.get("thread_source")
                if isinstance(source, str):
                    thread_source = source

    return Session(
        session_id=str(session_id),
        agent="codex",
        path=path.resolve(),
        repository=str(repository),
        started_at=started,
        last_activity_at=last_activity or modified,
        size_bytes=path.stat().st_size,
        event_count=event_count,
        status=status,
        title=(titles or {}).get(str(session_id), ""),
        origin=str(origin),
        thread_source=thread_source,
        last_event_type=last_event_type,
    )


def scan_codex(root: Path) -> list[Session]:
    if not root.is_dir():
        raise FileNotFoundError(f"Codex session directory not found: {root}")
    if (root / "sessions").is_dir():
        titles = load_session_titles(root / "session_index.jsonl")
        locations = ((root / "sessions", "active"), (root / "archived_sessions", "archived"))
    else:
        titles = {}
        locations = ((root, "active"),)
    return [
        read_codex_session(path, status, titles)
        for location, status in locations
        if location.is_dir()
        for path in sorted(location.rglob("*.jsonl"))
    ]


def _chatgpt_conversations(data: object, path: Path, source_entry: str) -> list[Session]:
    if not isinstance(data, list):
        raise ValueError("ChatGPT conversations JSON must contain a list")
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    sessions: list[Session] = []
    for conversation in data:
        if not isinstance(conversation, dict):
            continue
        session_id = conversation.get("conversation_id") or conversation.get("id")
        if not session_id:
            continue
        mapping = conversation.get("mapping")
        event_count = len(mapping) if isinstance(mapping, dict) else 0
        started = _unix_timestamp(conversation.get("create_time"), modified)
        updated = _unix_timestamp(conversation.get("update_time"), started)
        size_bytes = len(json.dumps(conversation, ensure_ascii=False).encode("utf-8"))
        sessions.append(
            Session(
                session_id=str(session_id),
                agent="chatgpt",
                path=path.resolve(),
                repository="",
                started_at=started,
                last_activity_at=max(started, updated),
                size_bytes=size_bytes,
                event_count=event_count,
                status="imported",
                title=str(conversation.get("title") or ""),
                origin="ChatGPT export",
                thread_source="chat",
                source_entry=source_entry,
            )
        )
    return sessions


def _unix_timestamp(value: object, fallback: datetime) -> datetime:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return fallback
    try:
        return datetime.fromtimestamp(value, timezone.utc)
    except (OSError, OverflowError, ValueError):
        return fallback


def scan_chatgpt_export(source: Path) -> list[Session]:
    if not source.exists():
        raise FileNotFoundError(f"ChatGPT export not found: {source}")
    sessions: dict[str, Session] = {}
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            names = [
                name
                for name in archive.namelist()
                if Path(name).name.lower().startswith("conversations")
                and Path(name).suffix.lower() == ".json"
            ]
            for name in names:
                # ponytail: stdlib loads the full export; add streaming only if real exports need it.
                data = json.load(archive.open(name))
                for session in _chatgpt_conversations(data, source, name):
                    sessions[session.session_id] = session
    else:
        paths = [source] if source.is_file() else sorted(source.rglob("conversations*.json"))
        for path in paths:
            with path.open(encoding="utf-8", errors="replace") as stream:
                data = json.load(stream)
            for session in _chatgpt_conversations(data, path, ""):
                sessions[session.session_id] = session
    if not sessions:
        raise ValueError("No ChatGPT conversations found in the export")
    return list(sessions.values())


def _chatgpt_export_data(session: Session) -> object:
    if session.source_entry:
        with zipfile.ZipFile(session.path) as archive:
            return json.load(archive.open(session.source_entry))
    with session.path.open(encoding="utf-8", errors="replace") as stream:
        return json.load(stream)


def extract_chatgpt_transcript(session: Session, max_chars: int = 24_000) -> str:
    if max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    data = _chatgpt_export_data(session)
    if not isinstance(data, list):
        return ""
    conversation = next(
        (
            item
            for item in data
            if isinstance(item, dict)
            and str(item.get("conversation_id") or item.get("id") or "")
            == session.session_id
        ),
        None,
    )
    if not conversation or not isinstance(conversation.get("mapping"), dict):
        return ""
    mapping = conversation["mapping"]
    nodes: list[dict] = []
    current = conversation.get("current_node")
    seen: set[str] = set()
    while isinstance(current, str) and current in mapping and current not in seen:
        seen.add(current)
        node = mapping[current]
        if not isinstance(node, dict):
            break
        nodes.append(node)
        current = node.get("parent")
    nodes.reverse()
    if not nodes:
        nodes = [node for node in mapping.values() if isinstance(node, dict)]
        nodes.sort(
            key=lambda node: (
                node["message"].get("create_time") or 0
                if isinstance(node.get("message"), dict)
                else 0
            )
        )

    chunks: list[str] = []
    for node in nodes:
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        author = message.get("author") or {}
        content = message.get("content") or {}
        role = author.get("role") if isinstance(author, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if role not in {"user", "assistant"} or not isinstance(parts, list):
            continue
        text = "\n".join(part for part in parts if isinstance(part, str)).strip()
        if text:
            chunks.append(f"{role}: {text}")
    return "\n\n".join(chunks)[-max_chars:]


def _create_sessions_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE sessions (
            record_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            session_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            repository TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_activity_at TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            event_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            title TEXT NOT NULL DEFAULT '',
            origin TEXT NOT NULL DEFAULT '',
            thread_source TEXT NOT NULL DEFAULT '',
            source_entry TEXT NOT NULL DEFAULT '',
            last_event_type TEXT NOT NULL DEFAULT ''
        )
        """
    )


def _ensure_schema(connection: sqlite3.Connection) -> None:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sessions'"
    ).fetchone()
    if not table:
        _create_sessions_table(connection)
        return

    existing = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
    if "record_id" not in existing:
        connection.execute("ALTER TABLE sessions RENAME TO sessions_legacy")
        _create_sessions_table(connection)
        optional = {
            "status": "'active'",
            "title": "''",
            "origin": "''",
            "thread_source": "''",
            "source_entry": "''",
            "last_event_type": "''",
        }
        values = [
            "agent || ':' || session_id || ':' || path",
            "path",
            "session_id",
            "agent",
            "repository",
            "started_at",
            "last_activity_at",
            "size_bytes",
            "event_count",
            *(name if name in existing else default for name, default in optional.items()),
        ]
        connection.execute(
            """
            INSERT INTO sessions (
                record_id, path, session_id, agent, repository, started_at,
                last_activity_at, size_bytes, event_count, status, title,
                origin, thread_source, source_entry, last_event_type
            )
            SELECT """
            + ", ".join(values)
            + " FROM sessions_legacy"
        )
        connection.execute("DROP TABLE sessions_legacy")
        return

    for name, definition in (
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("title", "TEXT NOT NULL DEFAULT ''"),
        ("origin", "TEXT NOT NULL DEFAULT ''"),
        ("thread_source", "TEXT NOT NULL DEFAULT ''"),
        ("source_entry", "TEXT NOT NULL DEFAULT ''"),
        ("last_event_type", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in existing:
            connection.execute(f"ALTER TABLE sessions ADD COLUMN {name} {definition}")


def sync_sessions(database: Path, sessions: list[Session], agent: str = "codex") -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    with _connect(database) as connection:
        _ensure_schema(connection)
        connection.execute("DELETE FROM sessions WHERE agent = ?", (agent,))
        connection.executemany(
            """
            INSERT INTO sessions (
                record_id, path, session_id, agent, repository, started_at,
                last_activity_at, size_bytes, event_count, status, title, origin,
                thread_source, source_entry, last_event_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"{session.agent}:{session.session_id}:{session.path}:{session.source_entry}",
                    str(session.path),
                    session.session_id,
                    session.agent,
                    session.repository,
                    session.started_at.isoformat(),
                    session.last_activity_at.isoformat(),
                    session.size_bytes,
                    session.event_count,
                    session.status,
                    session.title,
                    session.origin,
                    session.thread_source,
                    session.source_entry,
                    session.last_event_type,
                )
                for session in sessions
            ],
        )


def load_sessions(database: Path) -> list[Session]:
    if not database.is_file():
        raise FileNotFoundError(f"Session database not found: {database}. Run scan first.")
    with _connect(database) as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT session_id, agent, path, repository, started_at,
                   last_activity_at, size_bytes, event_count, status, title,
                   origin, thread_source, source_entry, last_event_type
            FROM sessions ORDER BY last_activity_at DESC
            """
        ).fetchall()
    return [
        Session(
            session_id=row[0],
            agent=row[1],
            path=Path(row[2]),
            repository=row[3],
            started_at=datetime.fromisoformat(row[4]),
            last_activity_at=datetime.fromisoformat(row[5]),
            size_bytes=row[6],
            event_count=row[7],
            status=row[8],
            title=row[9],
            origin=row[10],
            thread_source=row[11],
            source_entry=row[12],
            last_event_type=row[13],
        )
        for row in rows
    ]


def find_session(database: Path, session_id: str) -> Session:
    matches = [session for session in load_sessions(database) if session.session_id == session_id]
    if not matches:
        raise LookupError(f"Session not found: {session_id}")
    if len(matches) > 1:
        raise LookupError(f"Session id is not unique: {session_id}")
    return matches[0]


def age_days(session: Session, now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - session.last_activity_at).total_seconds() // 86_400))


def load_policy(path: Path) -> Policy:
    default = Policy(30, Path.home() / ".zar-agent-session-ops" / "archive", 24)
    if not path.is_file():
        return default

    with path.open("rb") as stream:
        values = tomllib.load(stream).get("policy", {})
    days = values.get("archive_after_days", default.archive_after_days)
    archive_dir = values.get("archive_dir", str(default.archive_dir))
    blocked_hours = values.get("blocked_after_hours", default.blocked_after_hours)
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("policy.archive_after_days must be a positive integer")
    if not isinstance(archive_dir, str) or not archive_dir.strip():
        raise ValueError("policy.archive_dir must be a non-empty path")
    if (
        isinstance(blocked_hours, bool)
        or not isinstance(blocked_hours, int)
        or blocked_hours < 1
    ):
        raise ValueError("policy.blocked_after_hours must be a positive integer")

    resolved_archive = Path(archive_dir).expanduser()
    if not resolved_archive.is_absolute():
        resolved_archive = path.parent / resolved_archive
    return Policy(days, resolved_archive.resolve(), blocked_hours)


def policy_candidates(
    sessions: list[Session], policy: Policy, now: datetime | None = None
) -> list[Session]:
    return [
        session
        for session in sessions
        if session.status == "active" and age_days(session, now) >= policy.archive_after_days
    ]


def blocked_candidates(
    sessions: list[Session], policy: Policy, now: datetime | None = None
) -> list[Session]:
    current = now or datetime.now(timezone.utc)
    threshold = policy.blocked_after_hours * 3_600
    return [
        session
        for session in sessions
        if session.agent == "codex"
        and session.status == "active"
        and session.last_event_type == "task_started"
        and (current - session.last_activity_at).total_seconds() >= threshold
    ]


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")


def markdown_report(
    sessions: list[Session], stale_days: int, now: datetime | None = None
) -> str:
    current = now or datetime.now(timezone.utc)
    stale = [
        session
        for session in sessions
        if session.status == "active" and age_days(session, current) >= stale_days
    ]
    lines = [
        "# Agent session report",
        "",
        f"Generated: {current.isoformat(timespec='seconds')}",
        "",
        f"- Sessions: {len(sessions)}",
        f"- Stored size: {format_size(sum(item.size_bytes for item in sessions))}",
        f"- Stale ({stale_days}+ days): {len(stale)}",
        "",
    ]
    lines.extend(_session_table(sessions, current))
    return "\n".join(lines) + "\n"


def blocked_report(
    sessions: list[Session], policy: Policy, now: datetime | None = None
) -> str:
    current = now or datetime.now(timezone.utc)
    blocked = blocked_candidates(sessions, policy, current)
    lines = [
        "# Potentially blocked Codex sessions",
        "",
        f"Generated: {current.isoformat(timespec='seconds')}",
        "",
        f"- Threshold: {policy.blocked_after_hours} hours",
        f"- Candidates: {len(blocked)}",
        "- Signal: last terminal event is `task_started` without later completion",
        "",
    ]
    lines.extend(_session_table(blocked, current))
    return "\n".join(lines) + "\n"


def weekly_report(sessions: list[Session], now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    start = current - timedelta(days=7)
    recent = [session for session in sessions if session.last_activity_at >= start]
    repositories = {session.repository for session in recent if session.repository}
    lines = [
        "# Weekly agent session report",
        "",
        f"Period: {start.date().isoformat()} to {current.date().isoformat()}",
        "",
        f"- Active sessions: {len(recent)}",
        f"- Repositories: {len(repositories)}",
        f"- Stored size: {format_size(sum(item.size_bytes for item in recent))}",
        "",
    ]
    lines.extend(_session_table(recent, current))
    return "\n".join(lines) + "\n"


def _session_table(sessions: list[Session], now: datetime) -> list[str]:
    lines = [
        "| Status | Origin | Session | Title | Repository | Last activity | Age | Size | Events |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for session in sessions:
        repository = (session.repository or "-").replace("|", "\\|")
        title = (session.title or "-").replace("|", "\\|")
        lines.append(
            f"| {session.status} | {session.origin or '-'} | `{session.session_id}` | "
            f"{title} | {repository} | "
            f"{session.last_activity_at.isoformat(timespec='seconds')} | "
            f"{age_days(session, now)} d | {format_size(session.size_bytes)} | "
            f"{session.event_count} |"
        )
    return lines


def extract_transcript(path: Path, max_chars: int = 24_000) -> str:
    if max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    chunks: deque[str] = deque()
    length = 0
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") != "response_item":
                continue
            payload = item.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            role = payload.get("role")
            if role not in {"user", "assistant"}:
                continue
            for content in payload.get("content") or []:
                if not isinstance(content, dict):
                    continue
                if content.get("type") not in {"input_text", "output_text"}:
                    continue
                message = content.get("text")
                if not isinstance(message, str) or not message.strip():
                    continue
                chunk = f"{role}: {message.strip()}"
                chunks.append(chunk)
                length += len(chunk) + 2
                while length > max_chars and len(chunks) > 1:
                    length -= len(chunks.popleft()) + 2
    return "\n\n".join(chunks)[-max_chars:]


def summarize_with_ollama(transcript: str, model: str, timeout: int = 120) -> str:
    if not transcript:
        raise ValueError("The session has no user or assistant text to summarize")
    body = json.dumps(
        {
            "model": model,
            "system": (
                "Summarize this coding-agent session as concise Markdown. Include "
                "Work completed, Technical decisions, Pending tasks, and Risks. "
                "Use only explicit evidence and write 'None identified' when needed."
            ),
            "prompt": transcript,
            "stream": False,
        }
    ).encode("utf-8")
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            summary = json.load(response).get("response", "").strip()
    except HTTPError as error:
        try:
            detail = json.load(error).get("error", str(error))
        except (json.JSONDecodeError, AttributeError):
            detail = str(error)
        raise RuntimeError(f"Ollama error: {detail}") from error
    except URLError as error:
        raise RuntimeError("Ollama is unavailable at http://127.0.0.1:11434") from error
    if not summary:
        raise RuntimeError("Ollama returned an empty summary")
    return summary


def archive_sessions(
    database: Path,
    sessions: list[Session],
    archive_dir: Path,
    apply: bool = False,
) -> list[tuple[Path, Path]]:
    if any(session.status != "active" for session in sessions):
        raise ValueError("Only active sessions can be archived")
    plans = [(session.path, archive_dir.resolve() / session.path.name) for session in sessions]
    if len({destination for _, destination in plans}) != len(plans):
        raise FileExistsError("Multiple sessions resolve to the same archive destination")
    for source, destination in plans:
        if not source.is_file():
            raise FileNotFoundError(f"Session file not found: {source}")
        if destination.exists():
            raise FileExistsError(f"Archive destination already exists: {destination}")
    if not apply:
        return plans

    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[tuple[Path, Path]] = []
    try:
        for source, destination in plans:
            shutil.move(str(source), destination)
            moved.append((source, destination))
        with _connect(database) as connection:
            connection.executemany(
                """
                DELETE FROM sessions
                WHERE agent = ? AND session_id = ? AND path = ? AND source_entry = ?
                """,
                [
                    (
                        session.agent,
                        session.session_id,
                        str(session.path),
                        session.source_entry,
                    )
                    for session in sessions
                ],
            )
    except (OSError, sqlite3.Error):
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                shutil.move(str(destination), source)
        raise
    return plans


def archive_session(
    database: Path, session_id: str, archive_dir: Path, apply: bool = False
) -> tuple[Path, Path]:
    return archive_sessions(
        database, [find_session(database, session_id)], archive_dir, apply
    )[0]
