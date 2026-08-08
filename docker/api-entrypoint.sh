#!/bin/sh
set -eu

if [ ! -f "$ZAR_SESSION_CONFIG" ]; then
  mkdir -p "$(dirname "$ZAR_SESSION_CONFIG")"
  printf '%s\n' \
    '[policy]' \
    'archive_after_days = 30' \
    'archive_dir = "/data/archive"' \
    'blocked_after_hours = 24' > "$ZAR_SESSION_CONFIG"
fi

python -m zar_agent_session_ops --db "$ZAR_SESSION_DB" --config "$ZAR_SESSION_CONFIG" scan --source "$ZAR_SESSION_SOURCE" --claude-source "$ZAR_CLAUDE_SOURCE"
exec uvicorn zar_agent_session_ops.api:app --host 0.0.0.0 --port 8000
