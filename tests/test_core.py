import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zar_agent_session_ops.core import (
    archive_session,
    load_sessions,
    markdown_report,
    scan_codex,
    sync_sessions,
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


if __name__ == "__main__":
    unittest.main()
