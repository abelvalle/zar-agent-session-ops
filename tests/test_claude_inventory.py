import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zar_agent_session_ops.core import scan_claude


class ClaudeInventoryTest(unittest.TestCase):
    def test_scans_valid_registry_entries_and_skips_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions = root / "sessions"
            sessions.mkdir()
            valid = sessions / "1234.json"
            started = datetime(2025, 8, 1, 12, 30, 45, tzinfo=timezone.utc)
            valid.write_text(
                json.dumps(
                    {
                        "pid": 1234,
                        "sessionId": "claude-session-1",
                        "cwd": "D:/projects/example",
                        "startedAt": int(started.timestamp() * 1000),
                        "version": "2.1.128",
                        "kind": "interactive",
                        "entrypoint": "claude-vscode",
                    }
                ),
                encoding="utf-8",
            )
            modified = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
            os.utime(valid, (modified.timestamp(), modified.timestamp()))
            (sessions / "broken.json").write_text("not json", encoding="utf-8")
            (sessions / "missing-id.json").write_text("{}", encoding="utf-8")

            found = scan_claude(root)

            self.assertEqual(1, len(found))
            session = found[0]
            self.assertEqual("claude-session-1", session.session_id)
            self.assertEqual("claude", session.agent)
            self.assertEqual("D:/projects/example", session.repository)
            self.assertEqual(started, session.started_at)
            self.assertEqual(modified, session.last_activity_at)
            self.assertEqual("registered", session.status)
            self.assertEqual("Claude Code (claude-vscode)", session.title)
            self.assertEqual("Claude Code 2.1.128", session.origin)
            self.assertEqual("interactive", session.thread_source)
            self.assertEqual(0, session.event_count)

    def test_returns_empty_inventory_when_registry_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual([], scan_claude(Path(directory)))


if __name__ == "__main__":
    unittest.main()
