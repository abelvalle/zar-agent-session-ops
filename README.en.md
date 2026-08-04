# Zar Agent Session Ops

[Español](README.md)

Open-source lifecycle management for local coding-agent sessions. Version
`0.7.0` provides a local Codex and ChatGPT inventory, conservative blocked
session signals, and a local read-only FastAPI API.

## Available features

- Discovers active and natively archived Codex sessions.
- Shows status, age, size, repository, origin, and task name.
- Distinguishes Codex Desktop, CLI, VS Code, automations, and subagents when
  those metadata are available.
- Stores normalized metadata only in SQLite.
- Produces general and weekly Markdown reports.
- Flags potentially blocked Codex sessions from terminal lifecycle events.
- Runs scanning, policy evaluation, and reports in one schedulable cycle.
- Exposes health, sessions, and blocked signals through a local API.
- Summarizes a session with a local Ollama model.
- Archives individual sessions or applies a configurable retention policy.
- Simulates every archive operation unless `--apply` is supplied.
- Imports metadata and on-demand transcripts from an official ChatGPT ZIP or
  JSON without copying conversations into the application database.

## Quick start

Requires Python 3.11 or newer.

```powershell
python -m pip install -e .
```

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops list --stale-days 7
python -m zar_agent_session_ops show SESSION_ID
python -m zar_agent_session_ops report --output sessions.md
python -m zar_agent_session_ops weekly --output weekly-sessions.md
python -m zar_agent_session_ops blocked --output blocked-sessions.md
python -m zar_agent_session_ops maintain
```

## Local API

The server listens exclusively on `127.0.0.1` and provides three read-only
operations:

- `GET /health`: status and version.
- `GET /sessions`: inventory with optional `agent` and `status` filters.
- `GET /blocked`: conservative potentially blocked signal.

```powershell
python -m zar_agent_session_ops serve
python -m zar_agent_session_ops serve --port 8080
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`. Responses
exclude the JSONL path and `source_entry`. This version has no authentication;
do not publish it through a proxy or expose it outside the local machine.

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
blocked_after_hours = 24
```

```powershell
python -m zar_agent_session_ops policy
python -m zar_agent_session_ops policy --apply
```

The policy never re-archives sessions already archived by Codex.

## Potentially blocked sessions

An active Codex session is flagged only when its latest terminal event is
`task_started`, no later completion or abort exists, and it has been inactive
longer than `blocked_after_hours`. This is an operational signal for human
review, not a semantic claim about the conversation.

```powershell
python -m zar_agent_session_ops blocked --output blocked-sessions.md
```

## Scheduled maintenance

`maintain` performs one Codex scan, retention-policy evaluation, and writes
`sessions.md`, `weekly.md`, and `blocked.md`. The default directory is
`%USERPROFILE%\.zar-agent-session-ops\reports`. Policy actions remain a dry run
unless `--apply-policy` is explicitly supplied.

```powershell
python -m zar_agent_session_ops maintain
python -m zar_agent_session_ops maintain --apply-policy
```

The project does not run its own daemon. On Windows, register a daily command
with Task Scheduler:

```powershell
$python = (Get-Command python).Source
$action = New-ScheduledTaskAction `
  -Execute $python `
  -Argument "-m zar_agent_session_ops maintain" `
  -WorkingDirectory "D:\path\to\zar-agent-session-ops"
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
Register-ScheduledTask -TaskName "ZarAgentSessionOps" -Action $action -Trigger $trigger
```

On Linux or macOS, the equivalent `cron` entry is:

```cron
0 9 * * * cd /path/to/zar-agent-session-ops && python3 -m zar_agent_session_ops maintain
```

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
- The API is GET-only, loopback-bound, and omits source-file paths.
- `--apply` is required before files can move.
- `maintain` also requires `--apply-policy` before files can move.
- Summaries are sent only to local Ollama.

## Development

```powershell
python -m pip install -e ".[test]"
python -B -m unittest discover -s tests -v
git diff --check
```

- `master`: latest stable and verified milestone.
- `develop`: active development.

Release details live in [CHANGELOG.md](CHANGELOG.md) and
[docs/milestones](docs/milestones).

## Next milestones

- Claude Code and OpenCode adapters once real fixtures are available.
- Local Angular dashboard over the existing API.
- GitHub Issues and Pull Requests integration.
