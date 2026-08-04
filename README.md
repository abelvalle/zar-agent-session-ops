# Zar Agent Session Ops

Open-source lifecycle management for local coding-agent sessions. The first
milestone discovers Codex sessions, stores their metadata in SQLite, reports
stale work, and archives selected sessions without deleting them.

## Quick start

Requires Python 3.11 or newer and has no runtime dependencies.

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops list --stale-days 7
python -m zar_agent_session_ops show SESSION_ID
python -m zar_agent_session_ops report --output sessions.md
```

Archiving is a dry run unless `--apply` is supplied:

```powershell
python -m zar_agent_session_ops archive SESSION_ID --archive-dir C:\agent-session-archive
python -m zar_agent_session_ops archive SESSION_ID --archive-dir C:\agent-session-archive --apply
```

Retention policies use `%USERPROFILE%\.zar-agent-session-ops\config.toml`:

```toml
[policy]
archive_after_days = 30
archive_dir = "archive"
```

Relative archive paths are resolved next to the config file. Policy execution
is also a dry run unless `--apply` is supplied:

```powershell
python -m zar_agent_session_ops policy
python -m zar_agent_session_ops policy --apply
```

By default the scanner reads `%USERPROFILE%\.codex\sessions` and stores its
index in `%USERPROFILE%\.zar-agent-session-ops\sessions.db`. Both paths are
configurable with `--source` and `--db`.

## Branches

- `master`: stable milestones.
- `develop`: active development.

## Roadmap

- Claude Code and OpenCode adapters, once real session fixtures are available.
- Optional local summaries through Ollama.
- Scheduled reports.
- FastAPI dashboard and GitHub integration after the local workflow is proven.

Session contents stay local. This milestone stores metadata only and never
modifies source sessions during scanning or reporting.
