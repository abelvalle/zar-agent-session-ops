import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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
                    {"status": "ok", "version": "0.9.0"},
                    client.get("/api/health").json(),
                )
                inventory = client.get(
                    "/api/sessions?agent=codex&status=active"
                ).json()
                self.assertEqual(1, inventory["count"])
                self.assertNotIn("path", inventory["sessions"][0])
                self.assertNotIn("source_entry", inventory["sessions"][0])
                blocked = client.get("/api/blocked").json()
                self.assertEqual(1, blocked["count"])
                self.assertEqual(24, blocked["threshold_hours"])
                with patch(
                    "zar_agent_session_ops.api.session_github_references",
                    return_value=[
                        {
                            "kind": "issue",
                            "owner": "acme",
                            "repository": "widgets",
                            "identifier": "12",
                            "url": "https://github.com/acme/widgets/issues/12",
                            "title": "Fix the widget",
                            "state": "open",
                        }
                    ],
                ):
                    github = client.get("/api/sessions/codex-1/github").json()
                self.assertEqual(1, github["count"])
                self.assertEqual("Fix the widget", github["references"][0]["title"])
                with patch(
                    "zar_agent_session_ops.api.session_github_references",
                    side_effect=FileNotFoundError("source missing"),
                ):
                    self.assertEqual(
                        422,
                        client.get("/api/sessions/codex-1/github").status_code,
                    )
                self.assertEqual(404, client.get("/api/sessions/missing/github").status_code)
                schema = client.get("/openapi.json").json()
                self.assertTrue(
                    all(
                        set(operations) == {"get"}
                        for operations in schema["paths"].values()
                    )
                )
                self.assertEqual(
                    {
                        "/api/health",
                        "/api/sessions",
                        "/api/blocked",
                        "/api/sessions/{session_id}/github",
                    },
                    set(schema["paths"]),
                )
                self.assertEqual("ok", client.get("/health").json()["status"])

            self.assertEqual("source remains untouched", source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
