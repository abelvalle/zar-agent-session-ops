import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from zar_agent_session_ops.cli import main
from zar_agent_session_ops.core import (
    extract_chatgpt_transcript,
    extract_session_transcript,
    load_sessions,
    scan_chatgpt_export,
)


class ChatGPTImportTest(unittest.TestCase):
    def test_imports_multiple_conversations_from_official_export_zip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / "chatgpt-export.zip"
            conversations = [
                self._conversation("chat-1", "Parser work", "Fix parser", "Parser fixed"),
                self._conversation("chat-2", "Docs work", "Write docs", "Docs written"),
            ]
            with zipfile.ZipFile(export, "w") as archive:
                archive.writestr("conversations.json", json.dumps(conversations))

            sessions = scan_chatgpt_export(export)
            self.assertEqual(2, len(sessions))
            self.assertEqual({"imported"}, {item.status for item in sessions})
            self.assertEqual({"ChatGPT export"}, {item.origin for item in sessions})

            database = root / "sessions.db"
            self._legacy_database(database)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    ["--db", str(database), "import-chatgpt", str(export)]
                )
            self.assertEqual(0, result)
            self.assertIn("Imported 2 ChatGPT conversations", output.getvalue())
            stored = load_sessions(database)
            self.assertEqual(
                {"chat-1", "chat-2"},
                {item.session_id for item in stored if item.agent == "chatgpt"},
            )
            self.assertIn("legacy-codex", {item.session_id for item in stored})
            first = next(item for item in stored if item.session_id == "chat-1")
            self.assertEqual("conversations.json", first.source_entry)
            self.assertEqual(
                "user: Fix parser\n\nassistant: Parser fixed",
                extract_chatgpt_transcript(first),
            )
            self.assertEqual(
                "user: Fix parser\n\nassistant: Parser fixed",
                extract_session_transcript(first),
            )

            handoff = root / "handoff.md"
            with patch(
                "zar_agent_session_ops.cli.session_handoff",
                return_value="# Session handoff\n",
            ) as generate:
                result = main(
                    [
                        "--db",
                        str(database),
                        "handoff",
                        "chat-1",
                        "--model",
                        "local-model",
                        "--output",
                        str(handoff),
                    ]
                )
            self.assertEqual(0, result)
            self.assertEqual("# Session handoff\n", handoff.read_text(encoding="utf-8"))
            self.assertEqual(
                "user: Fix parser\n\nassistant: Parser fixed",
                generate.call_args.args[1],
            )

    @staticmethod
    def _conversation(
        session_id: str, title: str, user_text: str, assistant_text: str
    ) -> dict:
        return {
            "id": session_id,
            "conversation_id": session_id,
            "title": title,
            "create_time": 1_754_300_000,
            "update_time": 1_754_300_100,
            "current_node": "assistant",
            "mapping": {
                "root": {
                    "id": "root",
                    "parent": None,
                    "children": ["user"],
                    "message": None,
                },
                "user": {
                    "id": "user",
                    "parent": "root",
                    "children": ["assistant"],
                    "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": [user_text]},
                    },
                },
                "assistant": {
                    "id": "assistant",
                    "parent": "user",
                    "children": [],
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {
                            "content_type": "text",
                            "parts": [assistant_text],
                        },
                    },
                },
            },
        }

    @staticmethod
    def _legacy_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                """
                CREATE TABLE sessions (
                    path TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    agent TEXT NOT NULL, repository TEXT NOT NULL,
                    started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL, event_count INTEGER NOT NULL,
                    status TEXT NOT NULL, title TEXT NOT NULL,
                    origin TEXT NOT NULL, thread_source TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "legacy.jsonl",
                    "legacy-codex",
                    "codex",
                    "D:/repo",
                    "2026-08-01T10:00:00+00:00",
                    "2026-08-01T11:00:00+00:00",
                    100,
                    2,
                    "active",
                    "Legacy Codex",
                    "Codex Desktop",
                    "user",
                ),
            )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
