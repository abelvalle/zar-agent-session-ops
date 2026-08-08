import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from zar_agent_session_ops.cli import main
from zar_agent_session_ops.core import load_sessions


class MaintenanceTest(unittest.TestCase):
    def test_reports_only_unfinished_inactive_sessions_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / ".codex"
            sessions_dir = codex_home / "sessions"
            sessions_dir.mkdir(parents=True)
            self._session(sessions_dir / "started.jsonl", "started", "task_started")
            self._session(sessions_dir / "complete.jsonl", "complete", "task_complete")

            config = root / "config.toml"
            config.write_text(
                """
[policy]
archive_after_days = 999
archive_dir = "archive"
blocked_after_hours = 24
""".strip(),
                encoding="utf-8",
            )
            database = root / "sessions.db"
            reports = root / "reports"
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "--db",
                        str(database),
                        "--config",
                        str(config),
                        "maintain",
                        "--source",
                        str(codex_home),
                        "--output-dir",
                        str(reports),
                    ]
                )

            self.assertEqual(0, result)
            self.assertIn("1 potentially blocked", output.getvalue())
            self.assertTrue((reports / "sessions.md").is_file())
            self.assertTrue((reports / "weekly.md").is_file())
            blocked = (reports / "blocked.md").read_text(encoding="utf-8")
            self.assertIn("`started`", blocked)
            self.assertNotIn("`complete`", blocked)
            self.assertEqual(
                {"started": "task_started", "complete": "task_complete"},
                {item.session_id: item.last_event_type for item in load_sessions(database)},
            )
            self.assertEqual(2, len(list(sessions_dir.glob("*.jsonl"))))

            with patch(
                "zar_agent_session_ops.cli.weekly_digest",
                return_value="# Weekly operational digest\n",
            ) as digest:
                result = main(
                    [
                        "--db",
                        str(database),
                        "--config",
                        str(config),
                        "maintain",
                        "--source",
                        str(codex_home),
                        "--output-dir",
                        str(reports),
                        "--model",
                        "local-model",
                    ]
                )
            self.assertEqual(0, result)
            self.assertEqual(
                "# Weekly operational digest\n",
                (reports / "weekly-digest.md").read_text(encoding="utf-8"),
            )
            digest.assert_called_once()
            self.assertEqual("local-model", digest.call_args.args[1])

    @staticmethod
    def _session(path: Path, session_id: str, terminal_event: str) -> None:
        events = [
            {
                "timestamp": "2026-01-01T10:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "cwd": "D:/repo",
                    "originator": "Codex Desktop",
                    "thread_source": "user",
                },
            },
            {
                "timestamp": "2026-01-01T11:00:00Z",
                "type": "event_msg",
                "payload": {"type": terminal_event},
            },
        ]
        path.write_text(
            "\n".join(json.dumps(event) for event in events), encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()
