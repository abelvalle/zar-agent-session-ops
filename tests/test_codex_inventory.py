import json
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from zar_agent_session_ops.core import (
    Policy,
    load_sessions,
    latest_codex_usage,
    policy_candidates,
    read_codex_session,
    scan_codex,
    sync_sessions,
)


class CodexInventoryTest(unittest.TestCase):
    def test_reads_latest_rate_limit_without_scanning_the_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions_dir = root / "sessions" / "2026" / "08" / "10"
            sessions_dir.mkdir(parents=True)
            valid = sessions_dir / (
                "rollout-2026-08-10T10-00-00-"
                "019fcc83-61e6-7aa0-b008-7eb5bc44ca08.jsonl"
            )
            self._session(valid, "ignored-meta-id", "Codex Desktop", "user")
            with valid.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\n"
                    + json.dumps(
                        {
                            "timestamp": "2026-08-10T14:17:52Z",
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "total_token_usage": {
                                        "input_tokens": 2000,
                                        "cached_input_tokens": 1500,
                                        "output_tokens": 500,
                                        "total_tokens": 2500,
                                    },
                                    "model_context_window": 258400,
                                },
                                "rate_limits": {
                                    "primary": {
                                        "used_percent": 96,
                                        "window_minutes": 10080,
                                        "resets_at": 1786834783,
                                    }
                                },
                            },
                        }
                    )
                )
            irrelevant = sessions_dir / "newer-without-usage.jsonl"
            irrelevant.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-08-10T14:18:00Z",
                        "type": "event_msg",
                        "payload": {"type": "task_started"},
                    }
                ),
                encoding="utf-8",
            )
            valid_mtime = valid.stat().st_mtime
            os.utime(irrelevant, (valid_mtime + 1, valid_mtime + 1))

            snapshot = latest_codex_usage(root)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(
                "019fcc83-61e6-7aa0-b008-7eb5bc44ca08", snapshot.session_id
            )
            self.assertEqual(96.0, snapshot.usage.rate_limit_used_percent)
            self.assertEqual(10_080, snapshot.usage.rate_limit_window_minutes)
            self.assertEqual(2500, snapshot.usage.total_tokens)

    def test_latest_rate_limit_is_unavailable_without_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(latest_codex_usage(Path(directory)))

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
            self.assertEqual([1500, 1500], [item.usage.total_tokens for item in sessions if item.usage])
            self.assertEqual(16.0, sessions[0].usage.rate_limit_used_percent)
            self.assertEqual(10_080, sessions[0].usage.rate_limit_window_minutes)

            database = root / "sessions.db"
            self._old_database(database)
            sync_sessions(database, sessions)
            stored = load_sessions(database)
            self.assertEqual({"active", "archived"}, {item.status for item in stored})
            self.assertEqual({1500}, {item.usage.total_tokens for item in stored if item.usage})
            candidates = policy_candidates(
                stored,
                Policy(1, root / "archive"),
                datetime(2026, 8, 6, tzinfo=timezone.utc),
            )
            self.assertEqual(["active-id"], [item.session_id for item in candidates])

    def test_reuses_unchanged_codex_sessions_and_reads_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions_dir = root / "sessions"
            sessions_dir.mkdir()
            path = sessions_dir / "session.jsonl"
            self._session(path, "session-id", "Codex Desktop", "user")

            known = scan_codex(root)
            with patch("zar_agent_session_ops.core.read_codex_session") as reader:
                unchanged = scan_codex(root, known)
            reader.assert_not_called()
            self.assertEqual(known, unchanged)

            legacy_known = [replace(known[0], usage=None, usage_scanned=False)]
            with patch(
                "zar_agent_session_ops.core.read_codex_session",
                wraps=read_codex_session,
            ) as reader:
                migrated = scan_codex(root, legacy_known)
            reader.assert_called_once()
            self.assertTrue(migrated[0].usage_scanned)
            self.assertEqual(1500, migrated[0].usage.total_tokens)

            with path.open("a", encoding="utf-8") as stream:
                stream.write(
                    "\n"
                    + json.dumps(
                        {
                            "timestamp": "2026-08-04T10:05:00Z",
                            "type": "event_msg",
                            "payload": {"type": "task_complete"},
                        }
                    )
                )
            changed = scan_codex(root, known)
            self.assertEqual(3, changed[0].event_count)
            self.assertEqual("task_complete", changed[0].last_event_type)

    @staticmethod
    def _session(path: Path, session_id: str, origin: str, thread_source: str) -> None:
        path.write_text(
            "\n".join(
                (
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
                    json.dumps(
                        {
                            "timestamp": "2026-08-04T10:01:00Z",
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "total_token_usage": {
                                        "input_tokens": 1200,
                                        "cached_input_tokens": 900,
                                        "output_tokens": 300,
                                        "reasoning_output_tokens": 100,
                                        "total_tokens": 1500,
                                    },
                                    "model_context_window": 258400,
                                },
                                "rate_limits": {
                                    "primary": {
                                        "used_percent": 16.0,
                                        "window_minutes": 10080,
                                        "resets_at": 1786770116,
                                    }
                                },
                            },
                        }
                    ),
                )
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
