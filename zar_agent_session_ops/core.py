from __future__ import annotations

import json
import shutil
import sqlite3
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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


@dataclass(frozen=True)
class Policy:
    archive_after_days: int
    archive_dir: Path


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


def read_codex_session(path: Path) -> Session:
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    started = modified
    last_activity: datetime | None = None
    session_id = path.stem
    repository = ""
    event_count = 0

    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            event_count += 1
            observed_at = _timestamp(item.get("timestamp"), modified)
            if event_count == 1:
                started = observed_at
            last_activity = max(last_activity or observed_at, observed_at)

            if item.get("type") == "session_meta":
                payload = item.get("payload") or {}
                session_id = payload.get("id") or payload.get("session_id") or session_id
                repository = payload.get("cwd") or repository

    return Session(
        session_id=str(session_id),
        agent="codex",
        path=path.resolve(),
        repository=str(repository),
        started_at=started,
        last_activity_at=last_activity or modified,
        size_bytes=path.stat().st_size,
        event_count=event_count,
    )


def scan_codex(root: Path) -> list[Session]:
    if not root.is_dir():
        raise FileNotFoundError(f"Codex session directory not found: {root}")
    return [read_codex_session(path) for path in sorted(root.rglob("*.jsonl"))]


def sync_sessions(database: Path, sessions: list[Session], agent: str = "codex") -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    with _connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                path TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                repository TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_activity_at TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                event_count INTEGER NOT NULL
            )
            """
        )
        connection.execute("DELETE FROM sessions WHERE agent = ?", (agent,))
        connection.executemany(
            """
            INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(session.path),
                    session.session_id,
                    session.agent,
                    session.repository,
                    session.started_at.isoformat(),
                    session.last_activity_at.isoformat(),
                    session.size_bytes,
                    session.event_count,
                )
                for session in sessions
            ],
        )


def load_sessions(database: Path) -> list[Session]:
    if not database.is_file():
        raise FileNotFoundError(f"Session database not found: {database}. Run scan first.")
    with _connect(database) as connection:
        rows = connection.execute(
            """
            SELECT session_id, agent, path, repository, started_at,
                   last_activity_at, size_bytes, event_count
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
    default = Policy(30, Path.home() / ".zar-agent-session-ops" / "archive")
    if not path.is_file():
        return default

    with path.open("rb") as stream:
        values = tomllib.load(stream).get("policy", {})
    days = values.get("archive_after_days", default.archive_after_days)
    archive_dir = values.get("archive_dir", str(default.archive_dir))
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("policy.archive_after_days must be a positive integer")
    if not isinstance(archive_dir, str) or not archive_dir.strip():
        raise ValueError("policy.archive_dir must be a non-empty path")

    resolved_archive = Path(archive_dir).expanduser()
    if not resolved_archive.is_absolute():
        resolved_archive = path.parent / resolved_archive
    return Policy(days, resolved_archive.resolve())


def policy_candidates(
    sessions: list[Session], policy: Policy, now: datetime | None = None
) -> list[Session]:
    return [
        session
        for session in sessions
        if age_days(session, now) >= policy.archive_after_days
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
    stale = [session for session in sessions if age_days(session, current) >= stale_days]
    lines = [
        "# Agent session report",
        "",
        f"Generated: {current.isoformat(timespec='seconds')}",
        "",
        f"- Sessions: {len(sessions)}",
        f"- Stored size: {format_size(sum(item.size_bytes for item in sessions))}",
        f"- Stale ({stale_days}+ days): {len(stale)}",
        "",
        "| Agent | Session | Repository | Last activity | Age | Size | Events |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for session in sessions:
        repository = (session.repository or "-").replace("|", "\\|")
        lines.append(
            f"| {session.agent} | `{session.session_id}` | {repository} | "
            f"{session.last_activity_at.isoformat(timespec='seconds')} | "
            f"{age_days(session, current)} d | {format_size(session.size_bytes)} | "
            f"{session.event_count} |"
        )
    return "\n".join(lines) + "\n"


def archive_sessions(
    database: Path,
    sessions: list[Session],
    archive_dir: Path,
    apply: bool = False,
) -> list[tuple[Path, Path]]:
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
                "DELETE FROM sessions WHERE path = ?",
                [(str(source),) for source, _ in plans],
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
