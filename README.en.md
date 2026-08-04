# Zar Agent Session Ops

[Español](README.md)

Open-source lifecycle management for local coding-agent sessions. Version
`0.5.0` provides complete local Codex inventory support and experimental import
from official ChatGPT data exports.

## Available features

- Discovers active and natively archived Codex sessions.
- Shows status, age, size, repository, origin, and task name.
- Distinguishes Codex Desktop, CLI, VS Code, automations, and subagents when
  those metadata are available.
- Stores normalized metadata only in SQLite.
- Produces general and weekly Markdown reports.
- Summarizes a session with a local Ollama model.
- Archives individual sessions or applies a configurable retention policy.
- Simulates every archive operation unless `--apply` is supplied.
- Imports metadata and on-demand transcripts from an official ChatGPT ZIP or
  JSON without copying conversations into the application database.

## Quick start

Requires Python 3.11 or newer and has no runtime dependencies.

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops list --stale-days 7
python -m zar_agent_session_ops show SESSION_ID
python -m zar_agent_session_ops report --output sessions.md
python -m zar_agent_session_ops weekly --output weekly-sessions.md
```

## Import a ChatGPT data export

Request an export under **ChatGPT > Settings > Data controls > Export**,
download the ZIP, and pass it directly to the command:

```powershell
python -m zar_agent_session_ops import-chatgpt C:\Downloads\chatgpt-export.zip
```

`conversations.json`, numbered conversation JSON files, and directories with
multiple `conversations*.json` files are also accepted. A new import replaces
only previous ChatGPT metadata; the Codex inventory remains untouched.

OpenAI confirms that the export contains chat history and may include
`conversations.json`, but it does not publish a contract for the internal JSON
schema. The adapter is therefore experimental and is not a live synchronization
mechanism. See the
[official export guide](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data).

By default, `scan` uses `CODEX_HOME` or `%USERPROFILE%\.codex` and reads:

- `sessions/`: active sessions.
- `archived_sessions/`: sessions archived by Codex.
- `session_index.jsonl`: task names.

The application index is stored in
`%USERPROFILE%\.zar-agent-session-ops\sessions.db`. Passing a `sessions`
directory directly remains supported for backwards compatibility:

```powershell
python -m zar_agent_session_ops scan --source C:\path\to\.codex\sessions
```

## Archiving and policies

Individual archives are dry runs by default:

```powershell
python -m zar_agent_session_ops archive SESSION_ID --archive-dir C:\agent-session-archive
python -m zar_agent_session_ops archive SESSION_ID --archive-dir C:\agent-session-archive --apply
```

Configure retention in
`%USERPROFILE%\.zar-agent-session-ops\config.toml`:

```toml
[policy]
archive_after_days = 30
archive_dir = "archive"
```

```powershell
python -m zar_agent_session_ops policy
python -m zar_agent_session_ops policy --apply
```

The policy never re-archives sessions already archived by Codex.

## Local Ollama summaries

The integration is pinned to `127.0.0.1`; remote endpoints are not accepted.
Only user and assistant messages are extracted, capped at the latest 24,000
characters by default.

```powershell
python -m zar_agent_session_ops summarize SESSION_ID --model qwen3:8b
```

## Security and privacy

- Scanning and reporting never modify the original JSONL files.
- The application database contains metadata, not transcripts.
- ChatGPT conversations remain in the original ZIP or JSON.
- The project does not query Codex's internal SQLite databases.
- `--apply` is required before files can move.
- Summaries are sent only to local Ollama.

## Development

```powershell
python -B -m unittest discover -s tests -v
git diff --check
```

- `master`: latest stable and verified milestone.
- `develop`: active development.

Release details live in [CHANGELOG.md](CHANGELOG.md) and
[docs/milestones](docs/milestones).

## Next milestones

- Claude Code and OpenCode adapters once real fixtures are available.
- Scheduled reports.
- FastAPI, dashboard, and GitHub integration after local collectors stabilize.
