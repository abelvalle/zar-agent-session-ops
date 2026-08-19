import json
import io
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from zar_agent_session_ops.api import create_app
from zar_agent_session_ops.core import Session, TokenUsage, scan_codex, sync_sessions


class ApiTest(unittest.TestCase):
    def test_reports_ollama_state_and_generates_with_an_installed_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "sessions.db"
            source = root / "session.jsonl"
            source.write_text(
                "\n".join(
                    json.dumps(item)
                    for item in (
                        {
                            "timestamp": "2026-08-11T10:00:00Z",
                            "type": "session_meta",
                            "payload": {"id": "summary-session", "cwd": "D:/repo"},
                        },
                        {
                            "timestamp": "2026-08-11T10:01:00Z",
                            "type": "response_item",
                            "payload": {
                                "role": "user",
                                "content": [{"type": "input_text", "text": "Fix the parser"}],
                            },
                        },
                    )
                ),
                encoding="utf-8",
            )
            sync_sessions(
                database,
                [
                    Session(
                        session_id="summary-session",
                        agent="codex",
                        path=source,
                        repository="D:/repo",
                        started_at=datetime(2026, 8, 11, 10, tzinfo=timezone.utc),
                        last_activity_at=datetime(2026, 8, 11, 10, 1, tzinfo=timezone.utc),
                        size_bytes=source.stat().st_size,
                        event_count=2,
                        title="Fix the parser",
                    )
                ],
            )

            with TestClient(create_app(database, root / "config.toml", root)) as client:
                record_key = client.get("/api/sessions").json()["sessions"][0]["record_key"]
                with patch(
                    "zar_agent_session_ops.api.list_ollama_models", return_value=[]
                ):
                    self.assertEqual("no_models", client.get("/api/ollama").json()["status"])
                    rejected = client.post(
                        f"/api/sessions/{record_key}/summary",
                        json={"model": "qwen3:8b"},
                    )
                    rejected_digest = client.post(
                        "/api/digests/weekly", json={"model": "qwen3:8b"}
                    )
                self.assertEqual(409, rejected.status_code)
                self.assertEqual(409, rejected_digest.status_code)

                with (
                    patch(
                        "zar_agent_session_ops.api.list_ollama_models",
                        return_value=["qwen3:8b"],
                    ),
                    patch(
                        "zar_agent_session_ops.api.summarize_with_ollama",
                        return_value="# Local summary\n\nParser work reviewed.",
                    ) as summarize,
                ):
                    state = client.get("/api/ollama").json()
                    response = client.post(
                        f"/api/sessions/{record_key}/summary",
                        json={"model": "qwen3:8b"},
                    )
                self.assertEqual(
                    {"status": "ready", "models": ["qwen3:8b"], "local_only": True},
                    state,
                )
                self.assertEqual(200, response.status_code)
                self.assertEqual("qwen3:8b", response.json()["model"])
                self.assertIn("# Local summary", response.json()["markdown"])
                self.assertIn("Fix the parser", summarize.call_args.args[0])

                with patch(
                    "zar_agent_session_ops.api.list_ollama_models",
                    side_effect=RuntimeError("offline"),
                ):
                    self.assertEqual(
                        "unavailable", client.get("/api/ollama").json()["status"]
                    )

                with (
                    patch(
                        "zar_agent_session_ops.api.list_ollama_models",
                        return_value=["qwen3:8b"],
                    ),
                    patch(
                        "zar_agent_session_ops.api.weekly_digest",
                        return_value="# Weekly operational digest\n\n## Pending tasks\n\nAdd tests.",
                    ) as digest,
                ):
                    generated = client.post(
                        "/api/digests/weekly", json={"model": "qwen3:8b"}
                    )
                self.assertEqual(200, generated.status_code)
                self.assertEqual("qwen3:8b", generated.json()["model"])
                self.assertEqual(1, digest.call_count)
                history = client.get("/api/digests/weekly").json()
                self.assertEqual(1, history["count"])
                self.assertIn("Pending tasks", history["digests"][0]["markdown"])
                self.assertNotIn(str(source), generated.text)

    def test_previews_and_confirms_a_chatgpt_export_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "sessions.db"
            sync_sessions(database, [])
            conversation = {
                "id": "chatgpt-upload-1",
                "conversation_id": "chatgpt-upload-1",
                "title": "Imported from web",
                "create_time": 1_754_300_000,
                "update_time": 1_754_300_100,
                "mapping": {},
            }
            export = io.BytesIO()
            with zipfile.ZipFile(export, "w") as archive:
                archive.writestr("conversations.json", json.dumps([conversation]))
            payload = export.getvalue()
            headers = {
                "content-type": "application/octet-stream",
                "x-filename": "chatgpt-export.zip",
            }

            with TestClient(
                create_app(database, root / "config.toml", root / "codex", root / "claude")
            ) as client:
                before = client.get("/api/sources").json()["sources"]
                chatgpt_before = next(item for item in before if item["id"] == "chatgpt")
                self.assertEqual("awaiting_import", chatgpt_before["status"])

                preview = client.post(
                    "/api/imports/chatgpt/preview", content=payload, headers=headers
                )
                self.assertEqual(200, preview.status_code)
                self.assertEqual(1, preview.json()["conversation_count"])
                self.assertEqual("Imported from web", preview.json()["conversations"][0]["title"])
                self.assertEqual(0, client.get("/api/sessions").json()["count"])
                self.assertFalse((root / "chatgpt-imports").exists())

                rejected = client.post(
                    "/api/imports/chatgpt", content=payload, headers=headers
                )
                self.assertEqual(422, rejected.status_code)
                imported = client.post(
                    "/api/imports/chatgpt",
                    content=payload,
                    headers={**headers, "x-confirmation": "IMPORT_CHATGPT"},
                )
                self.assertEqual(200, imported.status_code)
                self.assertEqual(1, imported.json()["imported_count"])
                self.assertTrue(imported.json()["stored_locally"])
                inventory = client.get("/api/sessions").json()
                self.assertEqual(1, inventory["count"])
                self.assertEqual("chatgpt", inventory["sessions"][0]["agent"])
                self.assertNotIn(str(root), imported.text)
                stored = list((root / "chatgpt-imports").glob("*.zip"))
                self.assertEqual(1, len(stored))
                after = client.get("/api/sources").json()["sources"]
                chatgpt_after = next(item for item in after if item["id"] == "chatgpt")
                self.assertEqual("imported", chatgpt_after["status"])
                self.assertEqual(1, chatgpt_after["session_count"])

    def test_live_usage_reads_the_latest_local_event_without_exposing_its_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_id = "019fcc83-61e6-7aa0-b008-7eb5bc44ca08"
            session_path = root / "sessions" / "2026" / "08" / "10" / f"rollout-{session_id}.jsonl"
            session_path.parent.mkdir(parents=True)
            observed_at = datetime.now(timezone.utc)
            session_path.write_text(
                json.dumps(
                    {
                        "timestamp": observed_at.isoformat(),
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
                ),
                encoding="utf-8",
            )

            with TestClient(
                create_app(root / "sessions.db", root / "config.toml", root)
            ) as client:
                response = client.get("/api/usage")

            self.assertEqual(200, response.status_code)
            payload = response.json()
            self.assertEqual("available", payload["status"])
            self.assertEqual(session_id, payload["session_id"])
            self.assertEqual(96.0, payload["usage"]["rate_limit_used_percent"])
            self.assertEqual(10_080, payload["usage"]["rate_limit_window_minutes"])
            self.assertFalse(payload["stale"])
            self.assertLess(payload["age_seconds"], 10)
            self.assertNotIn(str(root), response.text)

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
                        usage=TokenUsage(
                            observed_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                            input_tokens=1200,
                            cached_input_tokens=900,
                            output_tokens=300,
                            reasoning_output_tokens=100,
                            total_tokens=1500,
                            model_context_window=258400,
                            rate_limit_used_percent=16.0,
                            rate_limit_window_minutes=10080,
                            rate_limit_resets_at=datetime(
                                2026, 1, 8, tzinfo=timezone.utc
                            ),
                        ),
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
                    {"status": "ok", "version": "0.31.1"},
                    client.get("/api/health").json(),
                )
                self.assertEqual("unavailable", client.get("/api/usage").json()["status"])
                self.assertEqual(
                    {"archive_after_days": 30, "blocked_after_hours": 24},
                    client.get("/api/policy").json(),
                )
                rejected_policy = client.put(
                    "/api/policy",
                    json={"archive_after_days": 0, "blocked_after_hours": 12},
                )
                self.assertEqual(422, rejected_policy.status_code)
                saved_policy = client.put(
                    "/api/policy",
                    json={"archive_after_days": 45, "blocked_after_hours": 12},
                )
                self.assertEqual(200, saved_policy.status_code)
                self.assertEqual(45, saved_policy.json()["archive_after_days"])
                self.assertIn("archive_dir", config.read_text(encoding="utf-8"))
                preview = client.post("/api/maintenance/preview")
                self.assertEqual(200, preview.status_code)
                self.assertEqual("dry_run", preview.json()["mode"])
                self.assertEqual(1, preview.json()["archive_candidate_count"])
                history = client.get("/api/maintenance/history").json()
                self.assertEqual(1, history["count"])
                self.assertEqual(preview.json()["id"], history["runs"][0]["id"])
                client.put(
                    "/api/policy",
                    json={"archive_after_days": 30, "blocked_after_hours": 24},
                )
                inventory = client.get(
                    "/api/sessions?agent=codex&status=active"
                ).json()
                self.assertEqual(1, inventory["count"])
                self.assertNotIn("path", inventory["sessions"][0])
                self.assertNotIn("source_entry", inventory["sessions"][0])
                self.assertEqual(1500, inventory["sessions"][0]["usage"]["total_tokens"])
                self.assertEqual(
                    16.0,
                    inventory["sessions"][0]["usage"]["rate_limit_used_percent"],
                )
                session_record_key = inventory["sessions"][0]["record_key"]
                activity = client.get(
                    f"/api/sessions/{session_record_key}/activity"
                )
                self.assertEqual(200, activity.status_code)
                self.assertEqual("API test", activity.json()["objective"])
                self.assertEqual([], activity.json()["recent_activity"])
                self.assertNotIn(str(root), activity.text)
                handoff = client.get(
                    f"/api/sessions/{session_record_key}/handoff"
                )
                self.assertEqual(200, handoff.status_code)
                self.assertTrue(handoff.headers["content-type"].startswith("text/markdown"))
                self.assertEqual(
                    'inline; filename="session-handoff.md"',
                    handoff.headers["content-disposition"],
                )
                self.assertIn("# Session handoff", handoff.text)
                self.assertIn("API test", handoff.text)
                self.assertNotIn(str(root), handoff.text)
                self.assertNotIn("source remains untouched", handoff.text)
                blocked = client.get("/api/blocked").json()
                self.assertEqual(1, blocked["count"])
                self.assertEqual(24, blocked["threshold_hours"])
                self.assertEqual(0, blocked["dismissed_count"])
                record_key = blocked["sessions"][0]["record_key"]
                rejected = client.post(
                    f"/api/sessions/{record_key}/blocked-dismissal",
                    json={"confirmation": "not_blocked"},
                )
                self.assertEqual(422, rejected.status_code)
                dismissed = client.post(
                    f"/api/sessions/{record_key}/blocked-dismissal",
                    json={"confirmation": "NOT_BLOCKED"},
                )
                self.assertEqual(200, dismissed.status_code)
                self.assertTrue(dismissed.json()["reactivates_on_activity"])
                blocked = client.get("/api/blocked").json()
                self.assertEqual(0, blocked["count"])
                self.assertEqual(1, blocked["dismissed_count"])
                self.assertEqual(record_key, blocked["dismissed"][0]["record_key"])
                self.assertNotIn(
                    "codex-1", client.get("/api/reports/blocked").text
                )
                restored = client.post(
                    f"/api/blocked-dismissals/{record_key}/restore"
                )
                self.assertEqual(200, restored.status_code)
                self.assertEqual(1, client.get("/api/blocked").json()["count"])
                self.assertEqual(
                    404,
                    client.post(
                        f"/api/blocked-dismissals/{record_key}/restore"
                    ).status_code,
                )
                retention = client.get("/api/retention").json()
                self.assertEqual(1, retention["count"])
                self.assertEqual(30, retention["archive_after_days"])
                self.assertEqual("codex-1", retention["sessions"][0]["id"])
                self.assertNotIn("archive_dir", retention)
                for report_name in ("sessions", "weekly", "blocked"):
                    response = client.get(f"/api/reports/{report_name}")
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(
                        f'inline; filename="{report_name}.md"',
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
                        "/api/usage",
                        "/api/policy",
                        "/api/maintenance/history",
                        "/api/maintenance/preview",
                        "/api/sources",
                        "/api/ollama",
                        "/api/digests/weekly",
                        "/api/imports/chatgpt/preview",
                        "/api/imports/chatgpt",
                        "/api/sessions",
                        "/api/sessions/{record_key}/handoff",
                        "/api/sessions/{record_key}/activity",
                        "/api/sessions/{record_key}/summary",
                        "/api/blocked",
                        "/api/blocked-dismissals/{record_key}/restore",
                        "/api/archives",
                        "/api/retention",
                        "/api/sessions/{record_key}/archive",
                        "/api/sessions/{record_key}/blocked-dismissal",
                        "/api/archives/{record_key}/restore",
                        "/api/reports/{report_name}",
                        "/api/sessions/{session_id}/github",
                    },
                    set(schema["paths"]),
                )
                self.assertEqual("ok", client.get("/health").json()["status"])

            self.assertEqual("source remains untouched", source.read_text(encoding="utf-8"))

    def test_previews_confirms_and_restores_a_retention_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "codex"
            session_path = source / "sessions" / "old.jsonl"
            session_path.parent.mkdir(parents=True)
            session_path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-01-01T10:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "old-session", "cwd": "D:/repo"},
                    }
                ),
                encoding="utf-8",
            )
            database = root / "sessions.db"
            sync_sessions(database, scan_codex(source))
            config = root / "config.toml"
            config.write_text(
                '[policy]\narchive_after_days = 1\narchive_dir = "archive"\n',
                encoding="utf-8",
            )

            with TestClient(create_app(database, config, source, root / "claude")) as client:
                candidate = client.get("/api/retention").json()["sessions"][0]
                record_key = candidate["record_key"]
                preview = client.get(f"/api/sessions/{record_key}/archive")
                self.assertEqual(200, preview.status_code)
                self.assertEqual("old.jsonl", preview.json()["source_name"])
                self.assertNotIn(str(root), preview.text)
                self.assertTrue(session_path.exists())

                rejected = client.post(
                    f"/api/sessions/{record_key}/archive",
                    json={"confirmation": "archive"},
                )
                self.assertEqual(422, rejected.status_code)
                self.assertTrue(session_path.exists())

                archived = client.post(
                    f"/api/sessions/{record_key}/archive",
                    json={"confirmation": "ARCHIVE"},
                )
                self.assertEqual(200, archived.status_code)
                self.assertTrue(archived.json()["recovery_available"])
                self.assertFalse(session_path.exists())
                self.assertEqual(0, client.get("/api/sessions").json()["count"])
                recoveries = client.get("/api/archives").json()
                self.assertEqual(1, recoveries["count"])
                self.assertEqual("old-session", recoveries["archives"][0]["session_id"])

                restored = client.post(f"/api/archives/{record_key}/restore")
                self.assertEqual(200, restored.status_code)
                self.assertTrue(restored.json()["restored"])
                self.assertEqual("old-session", restored.json()["session"]["id"])
                self.assertTrue(session_path.exists())
                self.assertEqual(1, client.get("/api/sessions").json()["count"])
                self.assertEqual(0, client.get("/api/archives").json()["count"])

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
