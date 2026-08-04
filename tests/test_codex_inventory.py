import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zar_agent_session_ops.core import (
    Policy,
    load_sessions,
    policy_candidates,
    scan_codex,
    sync_sessions,
)


class CodexInventoryTest(unittest.TestCase):
    def test_scans_active_archived_titles_and_origins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "sessions" / "2026" / "08" / "04"
            archived = root / "archived_sessions"
            active.mkdir(parents=True)
            archived.mkdir()

            self._session(active / "active.jsonl", "active-id", "Codex Desktop", "user")
            self._session(archived / "archived.jsonl", "archived-id", "codex_exec", "automation")
            (root / "session_index.jsonl").write_text(
                "\n".join(
                    json.dumps({"id": session_id, "thread_name": title})
                    for session_id, title in (
                        ("active-id", "Active work"),
                        ("archived-id", "Archived work"),
                    )
                ),
                encoding="utf-8",
            )

            sessions = scan_codex(root)
            self.assertEqual(["active", "archived"], [item.status for item in sessions])
            self.assertEqual(["Active work", "Archived work"], [item.title for item in sessions])
            self.assertEqual(["Codex Desktop", "codex_exec"], [item.origin for item in sessions])
            self.assertEqual(["user", "automation"], [item.thread_source for item in sessions])

            database = root / "sessions.db"
            self._old_database(database)
            sync_sessions(database, sessions)
            stored = load_sessions(database)
            self.assertEqual({"active", "archived"}, {item.status for item in stored})
            candidates = policy_candidates(
                stored,
                Policy(1, root / "archive"),
                datetime(2026, 8, 6, tzinfo=timezone.utc),
            )
            self.assertEqual(["active-id"], [item.session_id for item in candidates])

    @staticmethod
    def _session(path: Path, session_id: str, origin: str, thread_source: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-08-04T10:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": session_id,
                        "cwd": "D:/repo",
                        "originator": origin,
                        "thread_source": thread_source,
                    },
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _old_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                """
                CREATE TABLE sessions (
                    path TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    agent TEXT NOT NULL, repository TEXT NOT NULL,
                    started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL, event_count INTEGER NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
