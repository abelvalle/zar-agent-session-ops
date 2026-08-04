from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    age_days,
    archive_session,
    archive_sessions,
    blocked_candidates,
    blocked_report,
    extract_chatgpt_transcript,
    extract_transcript,
    find_session,
    format_size,
    load_sessions,
    load_policy,
    markdown_report,
    policy_candidates,
    scan_codex,
    scan_chatgpt_export,
    summarize_with_ollama,
    sync_sessions,
    weekly_report,
)


DEFAULT_SOURCE = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
DEFAULT_DATABASE = Path.home() / ".zar-agent-session-ops" / "sessions.db"
DEFAULT_CONFIG = Path.home() / ".zar-agent-session-ops" / "config.toml"
DEFAULT_REPORT_DIR = DEFAULT_DATABASE.parent / "reports"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zar-session")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
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

    blocked = commands.add_parser("blocked", help="report potentially blocked sessions")
    blocked.add_argument("--output", type=Path, default=Path("blocked-sessions.md"))

    archive = commands.add_parser("archive", help="move a session to an archive")
    archive.add_argument("session_id")
    archive.add_argument("--archive-dir", type=Path, required=True)
    archive.add_argument("--apply", action="store_true")

    policy = commands.add_parser("policy", help="archive sessions matching the policy")
    policy.add_argument("--apply", action="store_true")

    weekly = commands.add_parser("weekly", help="write the last seven days as Markdown")
    weekly.add_argument("--output", type=Path, default=Path("weekly-sessions.md"))

    summarize = commands.add_parser("summarize", help="summarize one session with Ollama")
    summarize.add_argument("session_id")
    summarize.add_argument("--model", required=True)
    summarize.add_argument("--output", type=Path)
    summarize.add_argument("--max-chars", type=int, default=24_000)

    chatgpt = commands.add_parser(
        "import-chatgpt", help="import metadata from an official ChatGPT export"
    )
    chatgpt.add_argument("source", type=Path)

    maintain = commands.add_parser("maintain", help="run one scheduler-safe cycle")
    maintain.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    maintain.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    maintain.add_argument("--apply-policy", action="store_true")
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
                state = session.status
                if state == "active" and age_days(session, now) >= args.stale_days:
                    state = "stale"
                print(
                    f"{session.session_id}\t{state}\t{age_days(session, now)}d\t"
                    f"{format_size(session.size_bytes)}\t{session.origin or '-'}\t"
                    f"{session.title or session.repository or '-'}"
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
                        "status": session.status,
                        "title": session.title,
                        "origin": session.origin,
                        "thread_source": session.thread_source,
                        "source_entry": session.source_entry,
                        "last_event_type": session.last_event_type,
                    },
                    indent=2,
                )
            )
        elif args.command == "report":
            args.output.write_text(
                markdown_report(load_sessions(args.db), args.stale_days), encoding="utf-8"
            )
            print(f"Report written to {args.output.resolve()}")
        elif args.command == "blocked":
            policy = load_policy(args.config)
            sessions = load_sessions(args.db)
            args.output.write_text(
                blocked_report(sessions, policy), encoding="utf-8"
            )
            print(
                f"Blocked report written to {args.output.resolve()} "
                f"({len(blocked_candidates(sessions, policy))} candidates)"
            )
        elif args.command == "archive":
            source, destination = archive_session(
                args.db, args.session_id, args.archive_dir, args.apply
            )
            action = "Archived" if args.apply else "Dry run"
            print(f"{action}: {source} -> {destination}")
        elif args.command == "policy":
            policy = load_policy(args.config)
            sessions = policy_candidates(load_sessions(args.db), policy)
            plans = archive_sessions(args.db, sessions, policy.archive_dir, args.apply)
            action = "Archived" if args.apply else "Candidate"
            for source, destination in plans:
                print(f"{action}: {source} -> {destination}")
            print(f"{action} sessions: {len(plans)}")
        elif args.command == "weekly":
            args.output.write_text(weekly_report(load_sessions(args.db)), encoding="utf-8")
            print(f"Weekly report written to {args.output.resolve()}")
        elif args.command == "summarize":
            session = find_session(args.db, args.session_id)
            if session.agent == "chatgpt":
                transcript = extract_chatgpt_transcript(session, args.max_chars)
            else:
                transcript = extract_transcript(session.path, args.max_chars)
            summary = summarize_with_ollama(
                transcript, args.model
            )
            if args.output:
                args.output.write_text(summary + "\n", encoding="utf-8")
                print(f"Summary written to {args.output.resolve()}")
            else:
                print(summary)
        elif args.command == "import-chatgpt":
            sessions = scan_chatgpt_export(args.source)
            sync_sessions(args.db, sessions, agent="chatgpt")
            print(f"Imported {len(sessions)} ChatGPT conversations into {args.db}")
        elif args.command == "maintain":
            sync_sessions(args.db, scan_codex(args.source))
            policy = load_policy(args.config)
            sessions = load_sessions(args.db)
            candidates = policy_candidates(sessions, policy)
            archive_sessions(
                args.db, candidates, policy.archive_dir, args.apply_policy
            )
            if args.apply_policy:
                sessions = load_sessions(args.db)
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / "sessions.md").write_text(
                markdown_report(sessions, policy.archive_after_days), encoding="utf-8"
            )
            (args.output_dir / "weekly.md").write_text(
                weekly_report(sessions), encoding="utf-8"
            )
            blocked = blocked_candidates(sessions, policy)
            (args.output_dir / "blocked.md").write_text(
                blocked_report(sessions, policy), encoding="utf-8"
            )
            action = "archived" if args.apply_policy else "archive candidates"
            print(
                f"Maintenance complete: {len(sessions)} sessions, "
                f"{len(candidates)} {action}, {len(blocked)} potentially blocked"
            )
        return 0
    except (
        FileNotFoundError,
        FileExistsError,
        LookupError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(error, file=sys.stderr)
        return 1
