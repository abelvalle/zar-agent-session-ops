import json
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from zar_agent_session_ops.core import (
    Policy,
    archive_recoveries,
    archive_session,
    archive_session_reversible,
    archive_sessions,
    extract_transcript,
    load_sessions,
    load_policy,
    markdown_report,
    policy_candidates,
    restore_archived_session,
    scan_codex,
    session_handoff,
    summarize_with_ollama,
    sync_sessions,
    weekly_report,
    weekly_digest,
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

    def test_reversible_archive_keeps_a_receipt_and_restores_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sessions"
            source.mkdir()
            session_file = source / "session.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-07-01T10:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "reversible", "cwd": "D:/repo"},
                    }
                ),
                encoding="utf-8",
            )
            database = root / "sessions.db"
            sync_sessions(database, scan_codex(source))
            session = load_sessions(database)[0]
            archive_dir = root / "archive"

            _, destination, receipt = archive_session_reversible(
                database, session, archive_dir, apply=True
            )
            self.assertFalse(session_file.exists())
            self.assertTrue(destination.exists())
            self.assertTrue(receipt.exists())
            self.assertEqual([], load_sessions(database))
            self.assertEqual("reversible", archive_recoveries(archive_dir)[0]["session_id"])

            restored_id, restored_source, archived_source = restore_archived_session(
                receipt.name.removeprefix(".").removesuffix(".restore.json"),
                archive_dir,
            )
            self.assertEqual("reversible", restored_id)
            self.assertEqual(session_file.resolve(), restored_source)
            self.assertEqual(destination.resolve(), archived_source)
            self.assertTrue(session_file.exists())
            self.assertFalse(destination.exists())
            self.assertFalse(receipt.exists())
            self.assertEqual([], archive_recoveries(archive_dir))
            with self.assertRaisesRegex(ValueError, "Invalid session record key"):
                restore_archived_session("../outside", archive_dir)

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

    def test_generates_bounded_weekly_digest_from_latest_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_session(root / "old.jsonl", "old", "2026-07-01T10:00:00Z", "Old work")
            self._write_session(root / "recent.jsonl", "recent", "2026-08-07T10:00:00Z", "Recent work")
            newest = root / "newest.jsonl"
            self._write_session(
                newest,
                "newest",
                "2026-08-08T10:00:00Z",
                "Merged https://github.com/abelvalle/zar-agent-session-ops/pull/12",
            )
            source = newest.read_bytes()
            response = io.BytesIO(
                json.dumps({"response": "## Weekly summary\nParser delivered"}).encode()
            )
            with patch("zar_agent_session_ops.core.urlopen", return_value=response) as call:
                digest = weekly_digest(
                    scan_codex(root),
                    "local-model",
                    now=datetime(2026, 8, 8, 12, tzinfo=timezone.utc),
                    max_chars=400,
                    max_sessions=1,
                )

            self.assertIn("Sessions analyzed: 1", digest)
            request = json.loads(call.call_args.args[0].data)
            self.assertLessEqual(len(request["prompt"]), 400)
            self.assertIn("Session: newest", request["prompt"])
            self.assertIn("/pull/12", request["prompt"])
            self.assertNotIn("Recent work", request["prompt"])
            self.assertNotIn("Old work", request["prompt"])
            self.assertIn("Commits and pull requests", request["system"])
            self.assertEqual(source, newest.read_bytes())

    @staticmethod
    def _write_session(path: Path, session_id: str, timestamp: str, message: str) -> None:
        events = [
            {
                "timestamp": timestamp,
                "type": "session_meta",
                "payload": {"id": session_id, "cwd": "D:/repo"},
            },
            {
                "timestamp": timestamp,
                "type": "response_item",
                "payload": {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": message}],
                },
            },
        ]
        path.write_text(
            "\n".join(json.dumps(event) for event in events), encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()
