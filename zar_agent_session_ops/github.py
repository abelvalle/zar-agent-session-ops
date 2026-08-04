from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from . import __version__
from .core import Session, extract_chatgpt_transcript, extract_transcript


GITHUB_API_VERSION = "2026-03-10"
GITHUB_REFERENCE = re.compile(
    r"https://github\.com/"
    r"(?P<owner>[A-Za-z0-9.-]+)/(?P<repository>[A-Za-z0-9_.-]+)/"
    r"(?:(?P<route>issues|pull)/(?P<number>\d+)"
    r"|commit/(?P<sha>[0-9a-fA-F]{7,64}))",
    re.IGNORECASE,
)


def extract_github_references(text: str, max_refs: int = 20) -> list[dict[str, str]]:
    if max_refs < 1:
        raise ValueError("max_refs must be a positive integer")
    references: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for match in GITHUB_REFERENCE.finditer(text):
        route = (match.group("route") or "commit").lower()
        kind = "issue" if route == "issues" else route
        identifier = match.group("number") or match.group("sha") or ""
        key = (
            match.group("owner").lower(),
            match.group("repository").lower(),
            kind,
            identifier.lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        references.append(
            {
                "kind": kind,
                "owner": match.group("owner"),
                "repository": match.group("repository"),
                "identifier": identifier,
                "url": match.group(0),
            }
        )
        if len(references) == max_refs:
            break
    return references


def _api_url(reference: dict[str, str]) -> str:
    route = {"issue": "issues", "pull": "pulls", "commit": "commits"}[
        reference["kind"]
    ]
    parts = (
        quote(reference["owner"], safe=""),
        quote(reference["repository"], safe=""),
        route,
        quote(reference["identifier"], safe=""),
    )
    return f"https://api.github.com/repos/{parts[0]}/{parts[1]}/{parts[2]}/{parts[3]}"


def resolve_github_references(
    references: list[dict[str, str]], token: str | None = None
) -> list[dict[str, str]]:
    token = os.environ.get("GITHUB_TOKEN") if token is None else token
    resolved: list[dict[str, str]] = []
    for reference in references:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"zar-agent-session-ops/{__version__}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(_api_url(reference), headers=headers)
        item = reference.copy()
        try:
            with urlopen(request, timeout=10) as response:
                data = json.load(response)
            if reference["kind"] == "commit":
                commit = data.get("commit") if isinstance(data, dict) else None
                message = commit.get("message") if isinstance(commit, dict) else ""
                item["title"] = str(message or "").splitlines()[0]
                item["state"] = "available"
            else:
                item["title"] = str(data.get("title") or "")
                item["state"] = (
                    "merged"
                    if reference["kind"] == "pull" and data.get("merged")
                    else str(data.get("state") or "")
                )
        except HTTPError as error:
            item["error"] = f"GitHub API returned HTTP {error.code}"
        except (URLError, TimeoutError, json.JSONDecodeError):
            item["error"] = "GitHub API unavailable"
        resolved.append(item)
    return resolved


def session_github_references(
    session: Session, max_chars: int = 200_000
) -> list[dict[str, str]]:
    # ponytail: bounded tail scan; stream the full transcript if real misses appear.
    transcript = (
        extract_chatgpt_transcript(session, max_chars)
        if session.agent == "chatgpt"
        else extract_transcript(session.path, max_chars)
    )
    return resolve_github_references(extract_github_references(transcript))
