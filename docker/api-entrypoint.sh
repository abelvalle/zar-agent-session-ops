#!/bin/sh
set -eu

python -m zar_agent_session_ops --db "$ZAR_SESSION_DB" --config "$ZAR_SESSION_CONFIG" scan --source /codex
exec uvicorn zar_agent_session_ops.api:app --host 0.0.0.0 --port 8000
