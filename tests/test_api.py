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
            sync_sessions(
                database,
                [
                    Session(
                        session_id="claude-registered",
                        agent="claude",
                        path=source,
                        repository="D:/repo",
                        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        last_activity_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        size_bytes=21,
                        event_count=0,
                        status="registered",
                        title="Claude registry",
                    )
                ],
                agent="claude",
            )
            config = root / "config.toml"
            config.write_text(
                "[policy]\nblocked_after_hours = 24\narchive_after_days = 30\narchive_dir = 'archive'\n",
                encoding="utf-8",
            )

            with TestClient(
                create_app(database, config, root, root / "claude")
            ) as client:
                self.assertEqual(
                    {"status": "ok", "version": "0.18.0"},
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
                retention = client.get("/api/retention").json()
                self.assertEqual(1, retention["count"])
                self.assertEqual(30, retention["archive_after_days"])
                self.assertEqual("codex-1", retention["sessions"][0]["id"])
                self.assertNotIn("archive_dir", retention)
                for report_name in ("sessions", "weekly", "blocked"):
                    response = client.get(f"/api/reports/{report_name}")
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(
                        f'attachment; filename="{report_name}.md"',
                        response.headers["content-disposition"],
                    )
                    self.assertTrue(
                        response.headers["content-type"].startswith("text/markdown")
                    )
                    self.assertTrue(response.text.startswith("# "))
                self.assertEqual(
                    422, client.get("/api/reports/unknown").status_code
                )
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
                        "/api/retention",
                        "/api/reports/{report_name}",
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
            claude_source = root / "claude"
            claude_session = claude_source / "sessions" / "1234.json"
            claude_session.parent.mkdir(parents=True)
            claude_session.write_text(
                json.dumps(
                    {
                        "sessionId": "claude-refreshed-id",
                        "cwd": "D:/claude-refreshed",
                        "startedAt": 1_754_041_845_000,
                        "version": "2.1.128",
                        "kind": "interactive",
                        "entrypoint": "claude-vscode",
                    }
                ),
                encoding="utf-8",
            )
            database = root / "sessions.db"
            sync_sessions(database, [])

            with TestClient(
                create_app(database, root / "config.toml", source, claude_source)
            ) as client:
                accepted = client.post("/api/refresh")
                self.assertEqual(202, accepted.status_code)
                self.assertEqual("running", accepted.json()["status"])
                completed = client.get("/api/refresh").json()
                self.assertEqual("completed", completed["status"])
                self.assertEqual(2, completed["count"])
                self.assertEqual(2, completed["updated"])
                self.assertEqual(0, completed["reused"])
                self.assertGreaterEqual(completed["duration_seconds"], 0)
                inventory = client.get("/api/sessions").json()
                self.assertEqual(2, inventory["count"])
                sessions_by_id = {
                    session["id"]: session for session in inventory["sessions"]
                }
                self.assertEqual("codex", sessions_by_id["refreshed-id"]["agent"])
                self.assertEqual(
                    "registered",
                    sessions_by_id["claude-refreshed-id"]["status"],
                )

                client.post("/api/refresh")
                unchanged = client.get("/api/refresh").json()
                self.assertEqual("completed", unchanged["status"])
                self.assertEqual(0, unchanged["updated"])
                self.assertEqual(2, unchanged["reused"])

                source.rename(root / "missing-codex")
                with patch("zar_agent_session_ops.api.LOGGER.exception"):
                    client.post("/api/refresh")
                failed = client.get("/api/refresh").json()
                self.assertEqual("failed", failed["status"])
                self.assertNotIn(str(source), failed["error"])
                inventory = client.get("/api/sessions").json()
                self.assertEqual(2, inventory["count"])

            moved_session = root / "missing-codex" / "sessions" / "session.jsonl"
            self.assertEqual(session_source, moved_session.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
