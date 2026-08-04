# Zar Agent Session Ops

[English](README.en.md)

Plataforma open source para inspeccionar y gobernar el ciclo de vida de las
sesiones locales de agentes de programación. La versión `0.4.0` ofrece soporte
completo para el inventario local de Codex sin leer bases SQLite privadas.

## Funciones disponibles

- Detecta sesiones Codex activas y archivadas nativamente.
- Muestra estado, antigüedad, tamaño, repositorio, origen y nombre de la tarea.
- Distingue Codex Desktop, CLI, VS Code, automatizaciones y subagentes cuando
  esos metadatos existen.
- Guarda únicamente metadatos normalizados en SQLite.
- Genera informes generales y semanales en Markdown.
- Resume una sesión mediante un modelo Ollama local.
- Archiva sesiones individualmente o mediante una política configurable.
- Simula cualquier archivado salvo que se indique `--apply`.

## Inicio rápido

Requiere Python 3.11 o posterior y no tiene dependencias de ejecución.

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops list --stale-days 7
python -m zar_agent_session_ops show SESSION_ID
python -m zar_agent_session_ops report --output sessions.md
python -m zar_agent_session_ops weekly --output weekly-sessions.md
```

Por defecto, `scan` usa `CODEX_HOME` o `%USERPROFILE%\.codex` y consulta:

- `sessions/`: sesiones activas.
- `archived_sessions/`: sesiones archivadas por Codex.
- `session_index.jsonl`: nombres de las tareas.

El índice propio se guarda en
`%USERPROFILE%\.zar-agent-session-ops\sessions.db`. Para conservar el
comportamiento anterior también se puede pasar directamente un directorio
`sessions`:

```powershell
python -m zar_agent_session_ops scan --source C:\ruta\a\.codex\sessions
```

## Archivado y políticas

El archivado individual es una simulación por defecto:

```powershell
python -m zar_agent_session_ops archive SESSION_ID --archive-dir C:\agent-session-archive
python -m zar_agent_session_ops archive SESSION_ID --archive-dir C:\agent-session-archive --apply
```

La política se configura en
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

Las sesiones ya archivadas por Codex nunca se vuelven a archivar mediante la
política.

## Resúmenes locales con Ollama

La integración está fijada a `127.0.0.1`; no admite un endpoint remoto. Solo
extrae mensajes de usuario y asistente, limitados a los últimos 24.000
caracteres por defecto.

```powershell
python -m zar_agent_session_ops summarize SESSION_ID --model qwen3:8b
```

## Seguridad y privacidad

- El escaneo y los informes nunca modifican los JSONL originales.
- La base propia contiene metadatos, no transcripciones.
- El proyecto no consulta las bases SQLite internas de Codex.
- `--apply` es obligatorio para mover archivos.
- Los resúmenes solo se envían al Ollama local.

## Desarrollo

```powershell
python -B -m unittest discover -s tests -v
git diff --check
```

- `master`: último hito estable y verificado.
- `develop`: trabajo activo.

Los detalles de cada versión están en [CHANGELOG.md](CHANGELOG.md) y en
[docs/milestones](docs/milestones).

## Próximos hitos

- Importación experimental de conversaciones desde una exportación oficial de
  ChatGPT.
- Adaptadores de Claude Code y OpenCode cuando existan fixtures reales.
- Informes programados.
- FastAPI, dashboard e integración con GitHub después de estabilizar los
  colectores locales.
