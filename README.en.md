# Zar Agent Session Ops

[Español](README.md)

Open-source lifecycle management for local coding-agent sessions. Version
`0.18.0` makes Markdown reports readable inside the dashboard, keeps download
as an optional action, and preserves the operational view and incremental
refresh.

## Available features

- Discovers active and natively archived Codex sessions.
- Discovers metadata registered by Claude Code without assuming that the process
  is still active.
- Shows status, age, size, repository, origin, and task name.
- Distinguishes Codex Desktop, CLI, VS Code, automations, and subagents when
  those metadata are available.
- Stores normalized metadata only in SQLite.
- Produces general and weekly Markdown reports.
- Reads inventory, weekly activity, and blocked signals inside the dashboard,
  with an optional download for the selected Markdown report.
- Consolidates weekly work, decisions, pending tasks, risks, and GitHub
  relationships through local Ollama.
- Flags potentially blocked Codex sessions from terminal lifecycle events.
- Runs scanning, policy evaluation, and reports in one schedulable cycle.
- Exposes health, sessions, and blocked signals through a local API.
- Shows attention signals first and keeps the full inventory as a secondary
  lookup surface.
- Locates the exact session behind each signal in the filtered inventory.
- Resolves explicit GitHub Issue, Pull Request, and commit links.
- Summarizes a session with a local Ollama model.
- Generates a minimal Markdown handoff for a new Codex or ChatGPT session.
- Archives individual sessions or applies a configurable retention policy.
- Previews sessions that match retention policy without moving files.
- Simulates every archive operation unless `--apply` is supplied.
- Imports metadata and on-demand transcripts from an official ChatGPT ZIP or
  JSON without copying conversations into the application database.
- Packages the API and dashboard as a reproducible local Docker Compose stack.
- Refreshes Codex and the Claude Code registry through an incremental,
  non-blocking scan and reports duration, changed records, and reused metadata.

## Quick start

Requires Python 3.11 or newer.

```powershell
python -m pip install -e .
```

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops list --stale-days 7
python -m zar_agent_session_ops show SESSION_ID
python -m zar_agent_session_ops github SESSION_ID
python -m zar_agent_session_ops report --output sessions.md
python -m zar_agent_session_ops weekly --output weekly-sessions.md
python -m zar_agent_session_ops weekly-digest --model qwen3:8b
python -m zar_agent_session_ops blocked --output blocked-sessions.md
python -m zar_agent_session_ops handoff SESSION_ID --model qwen3:8b
python -m zar_agent_session_ops maintain
```

## Docker Compose

Docker Engine with Compose is required. In PowerShell, point the stack to the
available local directories and start it:

```powershell
$env:CODEX_HOME = "$HOME\.codex"
$env:CLAUDE_HOME = "$HOME\.claude" # optional
docker compose up --build -d
```

Open `http://127.0.0.1:4200`. On every start, the API scans the read-only
`/codex` and `/claude` mounts before becoming healthy. When `CLAUDE_HOME` is not
set, Compose mounts an empty source. Large inventories on Docker Desktop can
take several minutes. The dashboard is the only published service and proxies
`/api/**` to the API through the Compose network. SQLite and configuration live
in the persistent `zar-agent-session-ops_session-data` volume.

```powershell
docker compose logs -f
docker compose down
```

`docker compose down` preserves the volume. Set `ZAR_DASHBOARD_PORT` before
startup to choose another loopback port. `GITHUB_TOKEN` is optional; Compose
passes it into the API environment and the application does not store it.

The `Refresh` button starts a new background scan. Codex metadata is reused for
JSONL files whose size and status have not changed; new, changed, or moved files
are read again. The UI then reports duration, changes, and reused records. The
API remains responsive and prevents two scans from running at the same time.

## Local API

The server listens exclusively on `127.0.0.1` and provides these operations:

- `GET /api/health`: status and version.
- `GET /api/refresh`: state of the latest requested scan.
- `POST /api/refresh`: starts a background Codex and Claude Code scan.
- `GET /api/sessions`: inventory with optional `agent` and `status` filters.
- `GET /api/blocked`: conservative potentially blocked signal.
- `GET /api/retention`: candidate preview based on local policy.
- `GET /api/reports/{report_name}`: downloads `sessions`, `weekly`, or `blocked`
  as Markdown.
- `GET /api/sessions/{session_id}/github`: explicit GitHub relationships.

```powershell
python -m zar_agent_session_ops serve
python -m zar_agent_session_ops serve --port 8080
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`. Responses
exclude the JSONL path and `source_entry`. This version has no authentication;
do not publish it through a proxy or expose it outside the local machine. The
unprefixed routes remain available for 0.7 compatibility.

## Local dashboard

Requires Node.js 22.22.3 or newer. Refresh the inventory and start the API:

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops serve
```

In another terminal:

```powershell
cd dashboard
npm install
npm start
```

Open `http://127.0.0.1:4200`. The development server proxies `/api/**` to the
local API, so CORS does not need to be enabled. The interface opens with an
attention queue for potentially blocked sessions and archive candidates,
explains each signal, and locates it in the filtered inventory. Its report reader
opens the weekly report by default and switches between weekly, blocked, and
inventory reports without leaving the page; download remains secondary. The UI
also provides status metrics, filters, pagination, on-demand GitHub lookup, plus
loading, error, and empty states. It adapts to desktop and mobile.

## GitHub relationships

The command and dashboard find explicit Issue, Pull Request, and commit links
within the latest 200,000 characters of user and assistant messages. They then
query `api.github.com` for title and state:

```powershell
python -m zar_agent_session_ops github SESSION_ID
```

Public repositories work without authentication. For private resources or a
higher request limit, set `GITHUB_TOKEN` in the environment before starting the
command or API. The token is neither stored nor returned to the dashboard.

A relationship is created only when the conversation contains a complete
GitHub URL. Ambiguous references such as `#123` and time-based commit attribution
are deliberately ignored. The transcript remains local: GitHub receives only
the owner, repository, and number or SHA already present in the URL.

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

## Local Codex and Claude Code sources

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

It also uses `CLAUDE_HOME` or `%USERPROFILE%\.claude` and reads only
`sessions/*.json`. Those records provide an identifier, working directory,
version, kind, and entrypoint, but neither a transcript nor reliable proof that
the process is still running. They therefore use the `registered` status and
are excluded from blocked signals, summaries, and policy-based archiving.
Invalid JSON files are skipped without stopping the inventory.

```powershell
python -m zar_agent_session_ops scan --claude-source C:\path\to\.claude
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

The dashboard and `GET /api/retention` expose only the threshold and candidate
metadata. They neither expose `archive_dir` nor move files; archiving still
requires `--apply` or `--apply-policy` through the CLI.

## Potentially blocked sessions

An active Codex session is flagged only when its latest terminal event is
`task_started`, no later completion or abort exists, and it has been inactive
longer than `blocked_after_hours`. This is an operational signal for human
review, not a semantic claim about the conversation.

```powershell
python -m zar_agent_session_ops blocked --output blocked-sessions.md
```

## Scheduled maintenance

`maintain` performs one Codex and Claude Code scan, retention-policy evaluation,
and writes `sessions.md`, `weekly.md`, and `blocked.md`. The default directory is
`%USERPROFILE%\.zar-agent-session-ops\reports`. Policy actions remain a dry run
unless `--apply-policy` is explicitly supplied. When `--model` is provided, the
cycle adds `weekly-digest.md` through one local Ollama request.

```powershell
python -m zar_agent_session_ops maintain
python -m zar_agent_session_ops maintain --model qwen3:8b
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

## Weekly operational digest

`weekly-digest` selects sessions active in the latest seven days, uses at most
the 12 most recent, and shares no more than 24,000 total characters with Ollama.
The result contains a summary, technical decisions, pending tasks, risks, and
commits or Pull Requests backed by explicit URLs.

```powershell
python -m zar_agent_session_ops weekly-digest --model qwen3:8b --output weekly-digest.md
```

`--max-sessions` and `--max-chars` can lower those limits. The source transcript
is not appended to the generated Markdown, and source files are never modified.

## Minimal-context handoff

`handoff` reuses local extraction and Ollama to retain only the goal, completed
work, decisions, pending tasks, risks, and first next action. It neither appends
the raw transcript to the result nor modifies the source session.

```powershell
python -m zar_agent_session_ops handoff SESSION_ID --model qwen3:8b --output session-handoff.md
```

In Codex, start a new task with `/new`, then attach or paste
`session-handoff.md`. In ChatGPT, open a new chat and attach the same file. Do
not use `codex fork` for this purpose: it creates another chat but preserves the
complete original transcript instead of reducing context.

## Security and privacy

- Scanning and reporting never modify the original JSON or JSONL files.
- The application database contains metadata, not transcripts.
- ChatGPT conversations remain in the original ZIP or JSON.
- Claude Code registry JSON is read only and is not copied as transcripts.
- The project does not query Codex's internal SQLite databases.
- The API is loopback-bound and omits source-file paths. Its only operational
  mutation, `POST /api/refresh`, rewrites only the application's SQLite index.
- GitHub integration sends only explicit identifiers to `api.github.com`.
- `--apply` is required before files can move.
- `maintain` also requires `--apply-policy` before files can move.
- Summaries, handoffs, and operational digests are sent only to local Ollama.
- Under Compose, Codex and Claude Code are mounted read-only, the API runs as UID
  10001, and only the dashboard publishes a port bound to `127.0.0.1`.

## Development

```powershell
python -m pip install -e ".[test]"
python -B -m unittest discover -s tests -v
cd dashboard
npm audit
npm run build
npm test
cd ..
$env:CODEX_HOME = "$HOME\.codex"
$env:CLAUDE_HOME = "$HOME\.claude"
docker compose config --quiet
docker compose build
git diff --check
```

- `master`: latest stable and verified milestone.
- `develop`: active development.

Release details live in [CHANGELOG.md](CHANGELOG.md) and
[docs/milestones](docs/milestones).

## Next milestones

- Confirmed archiving from the attention queue, with explicit preview and
  recovery.
- Claude Code history and transcripts, plus an OpenCode adapter, once real
  fixtures for those sources are available.
- Server-side pagination and authentication when usage moves beyond loopback.
