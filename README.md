# Zar Agent Session Ops

[English](README.en.md)

Plataforma open source para inspeccionar y gobernar el ciclo de vida de las
sesiones locales de agentes de programación. La versión `0.16.0` ofrece un
inventario local de Codex y ChatGPT, incorpora el registro de sesiones de Claude
Code y permite revisar la política de retención desde el dashboard local.

## Funciones disponibles

- Detecta sesiones Codex activas y archivadas nativamente.
- Descubre metadatos de sesiones registradas por Claude Code sin asumir que el
  proceso continúa activo.
- Muestra estado, antigüedad, tamaño, repositorio, origen y nombre de la tarea.
- Distingue Codex Desktop, CLI, VS Code, automatizaciones y subagentes cuando
  esos metadatos existen.
- Guarda únicamente metadatos normalizados en SQLite.
- Genera informes generales y semanales en Markdown.
- Descarga inventario, actividad semanal y posibles bloqueos desde el dashboard.
- Consolida trabajo, decisiones, pendientes, riesgos y relaciones GitHub de la
  semana mediante Ollama local.
- Señala sesiones Codex potencialmente bloqueadas mediante eventos terminales.
- Ejecuta escaneo, política e informes en un único ciclo programable.
- Expone salud, sesiones y posibles bloqueos mediante una API local.
- Presenta métricas, filtros, paginación y bloqueos en un dashboard adaptable.
- Resuelve enlaces explícitos a GitHub Issues, Pull Requests y commits.
- Resume una sesión mediante un modelo Ollama local.
- Genera un relevo Markdown mínimo para una nueva sesión Codex o ChatGPT.
- Archiva sesiones individualmente o mediante una política configurable.
- Previsualiza las sesiones que cumplirían la política sin mover archivos.
- Simula cualquier archivado salvo que se indique `--apply`.
- Importa metadatos y transcripciones bajo demanda desde un ZIP o JSON oficial
  de ChatGPT sin copiar las conversaciones a la base propia.
- Empaqueta la API y el dashboard en un stack local reproducible con Docker
  Compose.
- Actualiza Codex y el registro de Claude Code mediante un escaneo no bloqueante
  iniciado desde la API o el dashboard.

## Inicio rápido

Requiere Python 3.11 o posterior.

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

Requiere Docker Engine con Compose. En PowerShell, indica los directorios locales
disponibles y levanta el stack:

```powershell
$env:CODEX_HOME = "$HOME\.codex"
$env:CLAUDE_HOME = "$HOME\.claude" # opcional
docker compose up --build -d
```

Abre `http://127.0.0.1:4200`. En cada arranque, la API escanea los directorios
montados en `/codex` y `/claude` como solo lectura antes de quedar sana. Si
`CLAUDE_HOME` no está definido, Compose monta una fuente vacía. Con inventarios
grandes y Docker Desktop el arranque puede tardar varios minutos. El dashboard
es el único servicio publicado y redirige `/api/**` a la API dentro de la red de
Compose. SQLite y la configuración se conservan en el volumen
`zar-agent-session-ops_session-data`.

```powershell
docker compose logs -f
docker compose down
```

`docker compose down` conserva el volumen. Para usar otro puerto de loopback,
define `ZAR_DASHBOARD_PORT` antes de levantar el stack. `GITHUB_TOKEN` también
es opcional; Compose lo transmite al entorno de la API y la aplicación no lo
guarda.

El botón `Actualizar` inicia un nuevo escaneo en segundo plano. La API continúa
respondiendo durante el trabajo y evita ejecutar dos escaneos simultáneos.

## API local

El servidor escucha exclusivamente en `127.0.0.1` y ofrece estas operaciones:

- `GET /api/health`: estado y versión.
- `GET /api/refresh`: estado del último escaneo solicitado.
- `POST /api/refresh`: inicia un escaneo Codex y Claude Code en segundo plano.
- `GET /api/sessions`: inventario; admite los filtros `agent` y `status`.
- `GET /api/blocked`: señal conservadora de posibles bloqueos.
- `GET /api/retention`: vista previa de candidatas según la política local.
- `GET /api/reports/{report_name}`: descarga `sessions`, `weekly` o `blocked`
  como Markdown.
- `GET /api/sessions/{session_id}/github`: relaciones GitHub explícitas.

```powershell
python -m zar_agent_session_ops serve
python -m zar_agent_session_ops serve --port 8080
```

La documentación OpenAPI queda disponible en `http://127.0.0.1:8000/docs`.
Las respuestas no incluyen la ruta del JSONL ni `source_entry`. Esta versión no
incorpora autenticación: no debe publicarse mediante proxy ni exponerse fuera
del equipo local. Las rutas sin el prefijo `/api` se conservan por compatibilidad
con la versión 0.7.

## Dashboard local

Requiere Node.js 22.22.3 o posterior. Primero actualiza el inventario e inicia
la API:

```powershell
python -m zar_agent_session_ops scan
python -m zar_agent_session_ops serve
```

En otra terminal:

```powershell
cd dashboard
npm install
npm start
```

Abre `http://127.0.0.1:4200`. El servidor de desarrollo redirige `/api/**` a
la API local, por lo que no hace falta habilitar CORS. La interfaz incluye
métricas de estado, filtros, paginación, vista previa de retención, revisión de
posibles bloqueos, consulta GitHub bajo demanda, refresco real del inventario y
estados de carga, error y ausencia de datos. También descarga los tres informes
Markdown sin abrir ni copiar transcripciones. Se adapta a escritorio y móvil.

## Relaciones con GitHub

El comando y el dashboard buscan enlaces explícitos a Issues, Pull Requests y
commits en los últimos 200.000 caracteres de mensajes de usuario y asistente.
Después consultan `api.github.com` para obtener título y estado:

```powershell
python -m zar_agent_session_ops github SESSION_ID
```

Los repositorios públicos funcionan sin autenticación. Para consultar recursos
privados o ampliar el límite de peticiones, configura `GITHUB_TOKEN` en el
entorno antes de iniciar el comando o la API. El token no se guarda ni se
devuelve al dashboard.

La relación se crea solo cuando la conversación contiene una URL completa de
GitHub. No se interpretan referencias ambiguas como `#123` ni se atribuyen
commits por coincidencia temporal. La transcripción permanece local: únicamente
se envían a GitHub el propietario, repositorio y número o SHA ya presentes en
la URL.

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

## Fuentes locales Codex y Claude Code

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

También usa `CLAUDE_HOME` o `%USERPROFILE%\.claude` y lee exclusivamente
`sessions/*.json`. Esos registros aportan identificador, directorio de trabajo,
versión, tipo y punto de entrada, pero no una transcripción ni una prueba fiable
de que el proceso siga ejecutándose. Por eso se muestran con estado
`registered`/`Registrada` y quedan fuera de bloqueos, resúmenes y archivado por
política. Los JSON inválidos se ignoran sin interrumpir el inventario.

```powershell
python -m zar_agent_session_ops scan --claude-source C:\ruta\a\.claude
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

El dashboard y `GET /api/retention` muestran únicamente el umbral y los
metadatos de las candidatas. No exponen `archive_dir` ni ejecutan movimientos;
el archivado continúa requiriendo `--apply` o `--apply-policy` en la CLI.

## Sesiones potencialmente bloqueadas

Una sesión Codex activa se señala únicamente si su último evento terminal es
`task_started`, no existe un cierre o aborto posterior y ha superado
`blocked_after_hours` sin actividad. Es una señal operativa para revisión
humana, no una afirmación semántica sobre el contenido de la conversación.

```powershell
python -m zar_agent_session_ops blocked --output blocked-sessions.md
```

## Mantenimiento programado

`maintain` ejecuta una vez el escaneo Codex y Claude Code, la política de
retención y los informes `sessions.md`, `weekly.md` y `blocked.md`. Los escribe por defecto en
`%USERPROFILE%\.zar-agent-session-ops\reports`. La política se simula salvo que
se indique expresamente `--apply-policy`. Si se proporciona `--model`, añade
`weekly-digest.md` mediante una sola llamada al Ollama local.

```powershell
python -m zar_agent_session_ops maintain
python -m zar_agent_session_ops maintain --model qwen3:8b
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

## Informe operativo semanal

`weekly-digest` selecciona las sesiones con actividad en los últimos siete días,
usa como máximo las 12 más recientes y comparte un total máximo de 24.000
caracteres con Ollama. El resultado contiene resumen, decisiones técnicas,
pendientes, riesgos y commits o Pull Requests respaldados por URLs explícitas.

```powershell
python -m zar_agent_session_ops weekly-digest --model qwen3:8b --output weekly-digest.md
```

`--max-sessions` y `--max-chars` permiten reducir esos límites. La transcripción
no se concatena al Markdown generado y las fuentes nunca se modifican.

## Relevo de contexto mínimo

`handoff` reutiliza la extracción local y Ollama para producir únicamente el
objetivo, trabajo completado, decisiones, pendientes, riesgos y primera acción.
No concatena la transcripción original al resultado ni modifica la sesión fuente.

```powershell
python -m zar_agent_session_ops handoff SESSION_ID --model qwen3:8b --output session-handoff.md
```

Para Codex, inicia una tarea nueva con `/new` y adjunta o pega
`session-handoff.md`. Para ChatGPT, abre un chat nuevo y adjunta el mismo archivo.
No uses `codex fork` para este caso: crea otro chat, pero conserva la
transcripción original completa en vez de reducir el contexto.

## Seguridad y privacidad

- El escaneo y los informes nunca modifican los JSON o JSONL originales.
- La base propia contiene metadatos, no transcripciones.
- Las conversaciones ChatGPT permanecen dentro del ZIP o JSON original.
- Los registros JSON de Claude Code solo se leen y no se copian como
  transcripciones.
- El proyecto no consulta las bases SQLite internas de Codex.
- La API se liga a loopback y omite las rutas de archivos fuente. Su única
  mutación operativa, `POST /api/refresh`, reescribe solo el índice SQLite propio.
- La integración GitHub solo envía identificadores explícitos a `api.github.com`.
- `--apply` es obligatorio para mover archivos.
- `maintain` tampoco mueve archivos sin `--apply-policy`.
- Los resúmenes, relevos e informes operativos solo se envían al Ollama local.
- En Compose, Codex y Claude Code se montan como solo lectura, la API se ejecuta
  con UID 10001 y solo el dashboard publica un puerto ligado a `127.0.0.1`.

## Desarrollo

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

- `master`: último hito estable y verificado.
- `develop`: trabajo activo.

Los detalles de cada versión están en [CHANGELOG.md](CHANGELOG.md) y en
[docs/milestones](docs/milestones).

## Próximos hitos

- Historial y transcripciones Claude Code, y adaptador OpenCode, cuando existan
  fixtures reales de esas fuentes.
- Paginación de servidor y autenticación cuando el uso deje de ser local.
