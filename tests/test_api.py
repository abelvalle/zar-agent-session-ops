import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from zar_agent_session_ops.api import create_app
from zar_agent_session_ops.core import Session, sync_sessions


class ApiTest(unittest.TestCase):
    def test_read_only_inventory_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "sessions.db"
            source = root / "session.jsonl"
            source.write_text("source remains untouched", encoding="utf-8")
            sync_sessions(
                database,
                [
                    Session(
                        session_id="codex-1",
                        agent="codex",
                        path=source,
                        repository="D:/repo",
                        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        last_activity_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        size_bytes=21,
                        event_count=2,
                        title="API test",
                        last_event_type="task_started",
                    )
                ],
            )
            config = root / "config.toml"
            config.write_text(
                "[policy]\nblocked_after_hours = 24\narchive_after_days = 30\narchive_dir = 'archive'\n",
                encoding="utf-8",
            )

            with TestClient(create_app(database, config)) as client:
                self.assertEqual(
                    {"status": "ok", "version": "0.7.0"},
                    client.get("/health").json(),
                )
                inventory = client.get("/sessions?agent=codex&status=active").json()
                self.assertEqual(1, inventory["count"])
                self.assertNotIn("path", inventory["sessions"][0])
                self.assertNotIn("source_entry", inventory["sessions"][0])
                blocked = client.get("/blocked").json()
                self.assertEqual(1, blocked["count"])
                self.assertEqual(24, blocked["threshold_hours"])
                schema = client.get("/openapi.json").json()
                self.assertTrue(
                    all(
                        set(operations) == {"get"}
                        for operations in schema["paths"].values()
                    )
                )

            self.assertEqual("source remains untouched", source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
