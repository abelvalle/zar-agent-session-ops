import json
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from zar_agent_session_ops.core import (
    Policy,
    archive_session,
    archive_sessions,
    extract_transcript,
    load_sessions,
    load_policy,
    markdown_report,
    policy_candidates,
    scan_codex,
    session_handoff,
    summarize_with_ollama,
    sync_sessions,
    weekly_report,
)


class SessionFlowTest(unittest.TestCase):
    def test_scan_report_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sessions"
            source.mkdir()
            session_file = source / "session.jsonl"
            events = [
                {
                    "timestamp": "2026-07-01T10:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "session-1", "cwd": "D:/repo"},
                },
                {
                    "timestamp": "2026-07-02T10:00:00Z",
                    "type": "event_msg",
                    "payload": {"type": "task_complete"},
                },
            ]
            session_file.write_text(
                "\n".join(json.dumps(event) for event in events), encoding="utf-8"
            )

            database = root / "sessions.db"
            sessions = scan_codex(source)
            sync_sessions(database, sessions)
            stored = load_sessions(database)

            self.assertEqual(1, len(stored))
            self.assertEqual("session-1", stored[0].session_id)
            self.assertEqual("D:/repo", stored[0].repository)
            self.assertEqual(2, stored[0].event_count)

            report = markdown_report(
                stored, stale_days=7, now=datetime(2026, 7, 20, tzinfo=timezone.utc)
            )
            self.assertIn("Stale (7+ days): 1", report)
            self.assertIn("session-1", report)

            archive_dir = root / "archive"
            _, destination = archive_session(database, "session-1", archive_dir)
            self.assertTrue(session_file.exists())
            self.assertFalse(destination.exists())

            archive_session(database, "session-1", archive_dir, apply=True)
            self.assertFalse(session_file.exists())
            self.assertTrue(destination.exists())
            self.assertEqual([], load_sessions(database))

    def test_policy_loads_candidates_and_archives_as_one_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sessions"
            source.mkdir()
            for session_id, day in (("old", "01"), ("recent", "19")):
                (source / f"{session_id}.jsonl").write_text(
                    json.dumps(
                        {
                            "timestamp": f"2026-07-{day}T10:00:00Z",
                            "type": "session_meta",
                            "payload": {"id": session_id, "cwd": "D:/repo"},
                        }
                    ),
                    encoding="utf-8",
                )

            config = root / "config.toml"
            config.write_text(
                '[policy]\narchive_after_days = 7\narchive_dir = "archive"\n',
                encoding="utf-8",
            )
            policy = load_policy(config)
            self.assertEqual(Policy(7, root / "archive"), policy)

            database = root / "sessions.db"
            sync_sessions(database, scan_codex(source))
            candidates = policy_candidates(
                load_sessions(database),
                policy,
                now=datetime(2026, 7, 20, tzinfo=timezone.utc),
            )
            self.assertEqual(["old"], [session.session_id for session in candidates])

            plans = archive_sessions(database, candidates, policy.archive_dir)
            self.assertEqual(1, len(plans))
            self.assertTrue(plans[0][0].exists())

            archive_sessions(database, candidates, policy.archive_dir, apply=True)
            self.assertFalse(plans[0][0].exists())
            self.assertTrue(plans[0][1].exists())
            self.assertEqual(["recent"], [item.session_id for item in load_sessions(database)])

    def test_weekly_report_and_local_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_file = Path(directory) / "session.jsonl"
            events = [
                {
                    "timestamp": "2026-07-19T10:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "session-1", "cwd": "D:/repo"},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Fix the parser"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Parser fixed"}],
                    },
                },
            ]
            session_file.write_text(
                "\n".join(json.dumps(event) for event in events), encoding="utf-8"
            )
            transcript = extract_transcript(session_file)
            self.assertEqual("user: Fix the parser\n\nassistant: Parser fixed", transcript)

            session = scan_codex(Path(directory))[0]
            report = weekly_report(
                [session], now=datetime(2026, 7, 20, tzinfo=timezone.utc)
            )
            self.assertIn("Active sessions: 1", report)
            self.assertIn("session-1", report)

            response = io.BytesIO(json.dumps({"response": "# Work completed"}).encode())
            with patch("zar_agent_session_ops.core.urlopen", return_value=response) as call:
                summary = summarize_with_ollama(transcript, "local-model")
            self.assertEqual("# Work completed", summary)
            request = json.loads(call.call_args.args[0].data)
            self.assertEqual("local-model", request["model"])
            self.assertFalse(request["stream"])

    def test_generates_minimal_codex_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_file = Path(directory) / "session.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-08-04T10:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "session-1", "cwd": "D:/repo"},
                    }
                ),
                encoding="utf-8",
            )
            session = scan_codex(Path(directory))[0]
            response = io.BytesIO(
                json.dumps({"response": "## Goal\nContinue parser work"}).encode()
            )
            with patch("zar_agent_session_ops.core.urlopen", return_value=response) as call:
                handoff = session_handoff(
                    session, "user: Fix parser\n\nassistant: Parser fixed", "local-model"
                )

            self.assertIn("# Session handoff", handoff)
            self.assertIn("Source agent: `codex`", handoff)
            self.assertIn("Source session: `session-1`", handoff)
            self.assertIn("Repository: `D:/repo`", handoff)
            self.assertNotIn("user: Fix parser", handoff)
            request = json.loads(call.call_args.args[0].data)
            self.assertIn("minimal handoff", request["system"])
            self.assertEqual("user: Fix parser\n\nassistant: Parser fixed", request["prompt"])


if __name__ == "__main__":
    unittest.main()
