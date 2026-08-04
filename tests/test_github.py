import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from zar_agent_session_ops.core import Session
from zar_agent_session_ops.github import (
    extract_github_references,
    resolve_github_references,
    session_github_references,
)


class GitHubIntegrationTest(unittest.TestCase):
    def test_extracts_unique_explicit_references(self) -> None:
        text = " ".join(
            [
                "https://github.com/acme/widgets/issues/12",
                "https://github.com/acme/widgets/pull/34",
                "https://github.com/acme/widgets/commit/abcdef1234567",
                "https://github.com/acme/widgets/issues/12",
                "https://example.com/acme/widgets/issues/99",
            ]
        )

        references = extract_github_references(text)

        self.assertEqual(
            ["issue", "pull", "commit"],
            [item["kind"] for item in references],
        )
        self.assertEqual(
            ["12", "34", "abcdef1234567"],
            [item["identifier"] for item in references],
        )

    def test_resolves_public_metadata_with_versioned_read_requests(self) -> None:
        payloads = [
            {"title": "Fix the widget", "state": "open"},
            {"title": "Ship the widget", "state": "closed", "merged": True},
            {"commit": {"message": "Release widget\n\nDetails"}},
        ]
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _Response(payloads[len(requests) - 1])

        references = extract_github_references(
            " ".join(
                [
                    "https://github.com/acme/widgets/issues/12",
                    "https://github.com/acme/widgets/pull/34",
                    "https://github.com/acme/widgets/commit/abcdef1234567",
                ]
            )
        )
        with patch("zar_agent_session_ops.github.urlopen", fake_urlopen):
            resolved = resolve_github_references(references, token="secret")

        self.assertEqual(
            ["open", "merged", "available"],
            [item["state"] for item in resolved],
        )
        self.assertEqual("Release widget", resolved[2]["title"])
        self.assertTrue(all(timeout == 10 for _, timeout in requests))
        self.assertTrue(
            all(
                request.get_header("Authorization") == "Bearer secret"
                for request, _ in requests
            )
        )
        self.assertTrue(
            all(
                request.get_header("X-github-api-version") == "2026-03-10"
                for request, _ in requests
            )
        )

    def test_reads_session_transcript_without_modifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "session.jsonl"
            original = json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "See https://github.com/acme/widgets/issues/12",
                            }
                        ],
                    },
                }
            )
            source.write_text(original, encoding="utf-8")
            session = Session(
                session_id="session-1",
                agent="codex",
                path=source,
                repository="D:/repo",
                started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                last_activity_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                size_bytes=len(original),
                event_count=1,
            )
            with patch(
                "zar_agent_session_ops.github.resolve_github_references",
                side_effect=lambda references: references,
            ):
                references = session_github_references(session)
            self.assertEqual("12", references[0]["identifier"])
            self.assertEqual(original, source.read_text(encoding="utf-8"))

    def test_keeps_reference_when_github_cannot_resolve_it(self) -> None:
        reference = extract_github_references(
            "https://github.com/acme/widgets/issues/404"
        )
        error = HTTPError("https://api.github.com", 404, "Not Found", None, None)

        with patch("zar_agent_session_ops.github.urlopen", side_effect=error):
            resolved = resolve_github_references(reference, token="")

        self.assertEqual("404", resolved[0]["identifier"])
        self.assertEqual("GitHub API returned HTTP 404", resolved[0]["error"])


class _Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


if __name__ == "__main__":
    unittest.main()
