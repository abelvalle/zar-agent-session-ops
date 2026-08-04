FROM python:3.13.11-slim-trixie@sha256:2b9c9803c6a287cafa0a8c917211dddd23dcd2016f049690ee5219f5d3f1636e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ZAR_SESSION_CONFIG=/data/config.toml \
    ZAR_SESSION_DB=/data/sessions.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY zar_agent_session_ops ./zar_agent_session_ops
RUN pip install --no-cache-dir . \
    && useradd --uid 10001 --create-home app \
    && mkdir /data \
    && chown app:app /data

COPY docker/api-entrypoint.sh ./docker/api-entrypoint.sh

USER app

ENTRYPOINT ["/bin/sh", "/app/docker/api-entrypoint.sh"]
