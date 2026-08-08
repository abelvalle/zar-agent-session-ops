import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from zar_agent_session_ops.api import create_app
from zar_agent_session_ops.core import Session, sync_sessions


class ApiTest(unittest.TestCase):
    def test_inventory_and_github_endpoints(self) -> None:
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

            with TestClient(create_app(database, config, root)) as client:
                self.assertEqual(
                    {"status": "ok", "version": "0.13.0"},
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
                self.assertEqual(
                    {"get", "post"}, set(schema["paths"]["/api/refresh"])
                )
                self.assertEqual(
                    {
                        "/api/health",
                        "/api/refresh",
                        "/api/sessions",
                        "/api/blocked",
                        "/api/sessions/{session_id}/github",
                    },
                    set(schema["paths"]),
                )
                self.assertEqual("ok", client.get("/health").json()["status"])

            self.assertEqual("source remains untouched", source.read_text(encoding="utf-8"))

    def test_refreshes_inventory_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "codex"
            session_path = source / "sessions" / "session.jsonl"
            session_path.parent.mkdir(parents=True)
            session_source = json.dumps(
                {
                    "timestamp": "2026-08-04T10:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "refreshed-id",
                        "cwd": "D:/refreshed",
                        "originator": "Codex Desktop",
                        "thread_source": "user",
                    }
                }
            )
            session_path.write_text(session_source, encoding="utf-8")
            database = root / "sessions.db"
            sync_sessions(database, [])

            with TestClient(create_app(database, root / "config.toml", source)) as client:
                accepted = client.post("/api/refresh")
                self.assertEqual(202, accepted.status_code)
                self.assertEqual("running", accepted.json()["status"])
                completed = client.get("/api/refresh").json()
                self.assertEqual("completed", completed["status"])
                self.assertEqual(1, completed["count"])
                inventory = client.get("/api/sessions").json()
                self.assertEqual("refreshed-id", inventory["sessions"][0]["id"])

                source.rename(root / "missing-codex")
                with patch("zar_agent_session_ops.api.LOGGER.exception"):
                    client.post("/api/refresh")
                failed = client.get("/api/refresh").json()
                self.assertEqual("failed", failed["status"])
                self.assertNotIn(str(source), failed["error"])
                inventory = client.get("/api/sessions").json()
                self.assertEqual("refreshed-id", inventory["sessions"][0]["id"])

            moved_session = root / "missing-codex" / "sessions" / "session.jsonl"
            self.assertEqual(session_source, moved_session.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
