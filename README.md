# Zar Agent Session Ops

[English](README.en.md)

Plataforma open source para inspeccionar y gobernar el ciclo de vida de las
sesiones locales de agentes de programación. La versión `0.6.0` ofrece soporte
para el inventario local de Codex, detección conservadora de sesiones
potencialmente bloqueadas e importación experimental de exportaciones oficiales
de ChatGPT.

## Funciones disponibles

- Detecta sesiones Codex activas y archivadas nativamente.
- Muestra estado, antigüedad, tamaño, repositorio, origen y nombre de la tarea.
- Distingue Codex Desktop, CLI, VS Code, automatizaciones y subagentes cuando
  esos metadatos existen.
- Guarda únicamente metadatos normalizados en SQLite.
- Genera informes generales y semanales en Markdown.
- Señala sesiones Codex potencialmente bloqueadas mediante eventos terminales.
- Ejecuta escaneo, política e informes en un único ciclo programable.
- Resume una sesión mediante un modelo Ollama local.
- Archiva sesiones individualmente o mediante una política configurable.
- Simula cualquier archivado salvo que se indique `--apply`.
- Importa metadatos y transcripciones bajo demanda desde un ZIP o JSON oficial
  de ChatGPT sin copiar las conversaciones a la base propia.

## Inicio rápido

Requiere Python 3.11 o posterior y no tiene dependencias de ejecución.

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops list --stale-days 7
python -m zar_agent_session_ops show SESSION_ID
python -m zar_agent_session_ops report --output sessions.md
python -m zar_agent_session_ops weekly --output weekly-sessions.md
python -m zar_agent_session_ops blocked --output blocked-sessions.md
python -m zar_agent_session_ops maintain
```

## Importar una exportación de ChatGPT

Solicita la exportación en **ChatGPT > Configuración > Controles de datos >
Exportar**, descarga el ZIP y pásalo directamente al comando:

```powershell
python -m zar_agent_session_ops import-chatgpt C:\Descargas\chatgpt-export.zip
```

También se acepta `conversations.json`, un JSON numerado o un directorio con
varios archivos `conversations*.json`. Una nueva importación reemplaza solamente
los metadatos ChatGPT anteriores; el inventario Codex permanece intacto.

OpenAI confirma que la exportación contiene el historial y puede incluir
`conversations.json`, pero no publica un contrato para su estructura interna.
Por ello, este adaptador es experimental y no constituye sincronización en
tiempo real. Consulta la
[guía oficial de exportación](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data).

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
blocked_after_hours = 24
```

```powershell
python -m zar_agent_session_ops policy
python -m zar_agent_session_ops policy --apply
```

Las sesiones ya archivadas por Codex nunca se vuelven a archivar mediante la
política.

## Sesiones potencialmente bloqueadas

Una sesión Codex activa se señala únicamente si su último evento terminal es
`task_started`, no existe un cierre o aborto posterior y ha superado
`blocked_after_hours` sin actividad. Es una señal operativa para revisión
humana, no una afirmación semántica sobre el contenido de la conversación.

```powershell
python -m zar_agent_session_ops blocked --output blocked-sessions.md
```

## Mantenimiento programado

`maintain` ejecuta una vez el escaneo Codex, la política de retención y los
informes `sessions.md`, `weekly.md` y `blocked.md`. Los escribe por defecto en
`%USERPROFILE%\.zar-agent-session-ops\reports`. La política se simula salvo que
se indique expresamente `--apply-policy`.

```powershell
python -m zar_agent_session_ops maintain
python -m zar_agent_session_ops maintain --apply-policy
```

El proyecto no mantiene un daemon propio. Para una ejecución diaria en Windows,
puede registrarse el comando con el Programador de tareas:

```powershell
$python = (Get-Command python).Source
$action = New-ScheduledTaskAction `
  -Execute $python `
  -Argument "-m zar_agent_session_ops maintain" `
  -WorkingDirectory "D:\ruta\a\zar-agent-session-ops"
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
Register-ScheduledTask -TaskName "ZarAgentSessionOps" -Action $action -Trigger $trigger
```

En Linux o macOS, la alternativa equivalente con `cron` es:

```cron
0 9 * * * cd /ruta/a/zar-agent-session-ops && python3 -m zar_agent_session_ops maintain
```

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
- Las conversaciones ChatGPT permanecen dentro del ZIP o JSON original.
- El proyecto no consulta las bases SQLite internas de Codex.
- `--apply` es obligatorio para mover archivos.
- `maintain` tampoco mueve archivos sin `--apply-policy`.
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

- Adaptadores de Claude Code y OpenCode cuando existan fixtures reales.
- FastAPI, dashboard e integración con GitHub después de estabilizar los
  colectores locales.
