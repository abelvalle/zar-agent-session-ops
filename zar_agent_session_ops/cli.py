from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    age_days,
    archive_session,
    find_session,
    format_size,
    load_sessions,
    markdown_report,
    scan_codex,
    sync_sessions,
)


DEFAULT_SOURCE = Path.home() / ".codex" / "sessions"
DEFAULT_DATABASE = Path.home() / ".zar-agent-session-ops" / "sessions.db"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zar-session")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="index local Codex sessions")
    scan.add_argument("--source", type=Path, default=DEFAULT_SOURCE)

    listing = commands.add_parser("list", help="list indexed sessions")
    listing.add_argument("--stale-days", type=int, default=7)

    show = commands.add_parser("show", help="show one indexed session")
    show.add_argument("session_id")

    report = commands.add_parser("report", help="write a Markdown report")
    report.add_argument("--output", type=Path, default=Path("sessions.md"))
    report.add_argument("--stale-days", type=int, default=7)

    archive = commands.add_parser("archive", help="move a session to an archive")
    archive.add_argument("session_id")
    archive.add_argument("--archive-dir", type=Path, required=True)
    archive.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "scan":
            sessions = scan_codex(args.source)
            sync_sessions(args.db, sessions)
            print(f"Indexed {len(sessions)} Codex sessions in {args.db}")
        elif args.command == "list":
            now = datetime.now(timezone.utc)
            for session in load_sessions(args.db):
                state = "stale" if age_days(session, now) >= args.stale_days else "active"
                print(
                    f"{session.session_id}\t{state}\t{age_days(session, now)}d\t"
                    f"{format_size(session.size_bytes)}\t{session.repository or '-'}"
                )
        elif args.command == "show":
            session = find_session(args.db, args.session_id)
            print(
                json.dumps(
                    {
                        "session_id": session.session_id,
                        "agent": session.agent,
                        "path": str(session.path),
                        "repository": session.repository,
                        "started_at": session.started_at.isoformat(),
                        "last_activity_at": session.last_activity_at.isoformat(),
                        "size_bytes": session.size_bytes,
                        "event_count": session.event_count,
                    },
                    indent=2,
                )
            )
        elif args.command == "report":
            args.output.write_text(
                markdown_report(load_sessions(args.db), args.stale_days), encoding="utf-8"
            )
            print(f"Report written to {args.output.resolve()}")
        elif args.command == "archive":
            source, destination = archive_session(
                args.db, args.session_id, args.archive_dir, args.apply
            )
            action = "Archived" if args.apply else "Dry run"
            print(f"{action}: {source} -> {destination}")
        return 0
    except (FileNotFoundError, FileExistsError, LookupError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
