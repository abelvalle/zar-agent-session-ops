# Zar Agent Session Ops

[English](README.en.md)

Plataforma open source para inspeccionar y gobernar el ciclo de vida de las
sesiones locales de agentes de programación. La versión `0.29.0` muestra el
estado real de Ollama, detecta sus modelos instalados y permite generar y leer
un resumen local dentro de la ficha de una sesión.

## Funciones disponibles

- Detecta sesiones Codex activas y archivadas nativamente.
- Descubre metadatos de sesiones registradas por Claude Code sin asumir que el
  proceso continúa activo.
- Muestra estado, antigüedad, tamaño, repositorio, origen y nombre de la tarea.
- Busca sesiones al instante por título, repositorio, identificador, agente u
  origen y combina la consulta con los filtros de agente y estado.
- Distingue Codex Desktop, CLI, VS Code, automatizaciones y subagentes cuando
  esos metadatos existen.
- Guarda únicamente metadatos normalizados en SQLite.
- Genera informes generales y semanales en Markdown.
- Renderiza inventario, actividad semanal y posibles bloqueos como HTML legible
  dentro del dashboard; la descarga Markdown continúa siendo opcional.
- Extrae tokens de entrada, caché, salida y razonamiento registrados por Codex.
- Muestra el consumo acumulado por sesión y el último límite Codex observado,
  con porcentaje disponible, fecha de reinicio, antigüedad y aviso de dato
  obsoleto.
- Consolida trabajo, decisiones, pendientes, riesgos y relaciones GitHub de la
  semana mediante Ollama local.
- Señala sesiones Codex potencialmente bloqueadas mediante eventos terminales.
- Permite descartar falsos bloqueos, conserva la decisión en SQLite y reactiva
  la señal automáticamente cuando la sesión vuelve a tener actividad.
- Ejecuta escaneo, política e informes en un único ciclo programable.
- Edita desde la web los umbrales de bloqueo y retención, valida sus rangos y
  conserva el destino de archivo configurado.
- Ejecuta simulaciones de mantenimiento y guarda en SQLite sus recuentos y la
  política usada; el modo web no aplica archivados por lotes.
- Expone salud, sesiones y posibles bloqueos mediante una API local.
- Presenta primero las señales que requieren atención y deja el inventario como
  vista de consulta secundaria.
- Permite localizar desde cada señal su sesión exacta, desplaza el foco hasta su
  fila y la mantiene resaltada.
- Abre una ficha operativa con origen, tipo, eventos, tamaño, tokens y relaciones
  GitHub; el detalle conserva valor aunque no existan referencias GitHub.
- Lee bajo demanda hasta seis fragmentos recientes y muestra objetivo, último
  resultado, petición pendiente y siguiente acción sin guardar el transcript.
- Une metadatos, actividad y señales en un flujo de decisión visible; prioriza
  bloqueos sobre retención y conserva las confirmaciones antes de cambiar estado.
- Resuelve enlaces explícitos a GitHub Issues, Pull Requests y commits.
- Detecta si Ollama está listo, no tiene modelos o no está disponible, sin
  instalar ni descargar modelos automáticamente.
- Resume una sesión mediante un modelo Ollama ya instalado y muestra el
  Markdown dentro de su ficha, sin persistir el resultado.
- Genera un relevo Markdown base desde cualquier ficha con metadatos y contexto
  reciente acotado; Ollama sigue disponible como síntesis CLI opcional.
- Archiva sesiones individualmente o mediante una política configurable.
- Previsualiza las sesiones que cumplirían la política sin mover archivos.
- Permite revisar y confirmar el archivado desde la ficha operativa.
- Conserva recibos locales y muestra las sesiones archivadas recuperables en la
  cola de atención, incluso después de recargar la web.
- Simula cualquier archivado salvo que se indique `--apply`.
- Importa metadatos y transcripciones bajo demanda desde un ZIP o JSON oficial
  de ChatGPT sin copiar las conversaciones a la base propia.
- Muestra disponibilidad y número de sesiones por fuente; OpenCode declara
  expresamente su estado aún no configurado.
- Analiza una exportación ChatGPT antes de importarla, exige una segunda
  confirmación y conserva una copia local gestionada para consultas posteriores.
- Empaqueta la API y el dashboard en un stack local reproducible con Docker
  Compose.
- Actualiza Codex y el registro de Claude Code mediante un escaneo incremental
  no bloqueante e informa duración, registros cambiados y metadatos reutilizados.

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

Abre `http://127.0.0.1:4200`. En cada arranque, la API escanea `/codex` y
`/claude` antes de quedar sana. `/codex` se monta con escritura para permitir el
archivado confirmado; `/claude` continúa como solo lectura. Si `CLAUDE_HOME` no
está definido, Compose monta una fuente vacía. Con inventarios
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

El botón `Actualizar` consulta inmediatamente el último límite local de Codex e
inicia un nuevo escaneo en segundo plano. Codex reutiliza
los metadatos de JSONL cuyo tamaño y estado no han cambiado y vuelve a leer los
archivos nuevos, modificados o movidos. Al terminar, la web muestra duración,
cambios y reutilizaciones. La API continúa respondiendo durante el trabajo y
evita ejecutar dos escaneos simultáneos.

## API local

El servidor escucha exclusivamente en `127.0.0.1` y ofrece estas operaciones:

- `GET /api/health`: estado y versión.
- `GET /api/refresh`: estado del último escaneo solicitado.
- `POST /api/refresh`: inicia un escaneo Codex y Claude Code en segundo plano.
- `GET|PUT /api/policy`: consulta o actualiza los umbrales locales validados.
- `GET /api/sources`: disponibilidad y recuento por fuente, sin rutas locales.
- `GET /api/ollama`: disponibilidad y modelos instalados en el Ollama local.
- `POST /api/imports/chatgpt/preview`: valida un ZIP o JSON y muestra hasta diez
  conversaciones sin modificar el inventario.
- `POST /api/imports/chatgpt`: importa tras confirmar `IMPORT_CHATGPT`.
- `POST /api/maintenance/preview`: ejecuta y registra una simulación sin mover
  archivos.
- `GET /api/maintenance/history`: últimas diez simulaciones registradas.
- `GET /api/usage`: última instantánea local del límite Codex, su antigüedad y
  estado de obsolescencia; no reindexa el inventario ni expone rutas.
- `GET /api/sessions`: inventario con telemetría de tokens cuando existe; admite
  los filtros `agent` y `status`.
- `GET /api/sessions/{record_key}/activity`: ficha de actividad acotada de la
  sesión exacta, sin rutas fuente ni persistencia de mensajes.
- `GET /api/sessions/{record_key}/handoff`: relevo Markdown base de la sesión
  exacta, sin rutas fuente ni dependencia de Ollama.
- `POST /api/sessions/{record_key}/summary`: genera un resumen no persistente
  con un modelo que Ollama ya tenga instalado.
- `GET /api/blocked`: señales activas y descartadas de posibles bloqueos.
- `POST /api/sessions/{record_key}/blocked-dismissal`: descarta una señal tras
  confirmar `NOT_BLOCKED`.
- `POST /api/blocked-dismissals/{record_key}/restore`: reactiva una señal
  descartada.
- `GET /api/retention`: vista previa de candidatas según la política local.
- `GET /api/archives`: archivados con recibo de recuperación disponible.
- `GET /api/sessions/{record_key}/archive`: previsualiza un archivado concreto.
- `POST /api/sessions/{record_key}/archive`: archiva tras confirmar `ARCHIVE`.
- `POST /api/archives/{record_key}/restore`: restaura el archivo original.
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
la API local, por lo que no hace falta habilitar CORS. La interfaz abre con una
cola de atención para posibles bloqueos, candidatas a archivo y recuperaciones,
explica cada señal y permite localizarla en el inventario filtrado. El lector de
informes renderiza títulos, listas y tablas del Markdown dentro de la página y
permite alternar entre semanal, bloqueos e inventario; la descarga queda como
acción secundaria. `Revisar señal` lleva el foco a la fila exacta, la resalta y
abre la explicación de la heurística. Desde esa ficha se puede confirmar un
falso positivo y deshacerlo; la cola conserva las señales descartadas. `Ver
detalle` abre metadatos, consumo de tokens, relaciones GitHub y `Relevo para
continuar`. El relevo se renderiza en la ficha y ofrece copia y descarga
Markdown. Para una candidata Codex directa, `Revisar y archivar`
abre esa ficha, prepara una vista previa no destructiva y exige una confirmación
separada. `Todas las sesiones` permite buscar por título, repositorio,
identificador, agente u origen; combina la consulta con agente, estado y
paginación, y muestra el total filtrado. Las alertas limpian una búsqueda
incompatible antes de localizar su fila. La cola conserva `Restaurar` mientras
exista el recibo local. Se adapta a escritorio y móvil.

## Métricas de tokens y suscripción

Codex incluye eventos locales `token_count` con el acumulado de entrada, entrada
en caché, salida, razonamiento, total procesado y ventana de contexto. El escaneo
0.19 conserva solo esos contadores y sus tiempos en SQLite; no añade contenido de
la conversación. La primera actualización tras migrar vuelve a leer una vez los
JSONL existentes y las siguientes recuperan el escaneo incremental.

La interfaz deduplica por identificador de sesión para el total histórico. El
porcentaje usado, el disponible y el reinicio se leen aparte mediante
`GET /api/usage`, que recorre hacia atrás los JSONL más recientes hasta encontrar
la última instantánea válida. La hora observada siempre es visible y, tras 15
minutos sin una observación nueva, la interfaz la marca como obsoleta. `Actualizar`
recarga este dato de forma ligera antes de completar el escaneo general.

Ese porcentaje sigue siendo una observación local, no una consulta autenticada
a la cuenta. La [documentación oficial de Codex](https://learn.chatgpt.com/docs/pricing)
indica que los límites vigentes se consultan en el panel de uso o con `/status`
y que pueden aplicarse límites semanales. ChatGPT Work y Codex comparten uso,
créditos y límites, pero no existe una cuota fija de suscripción convertible a
un total de tokens. Claude Code, ChatGPT importado y sesiones antiguas pueden
mostrar `No disponible` cuando su fuente no contiene estos eventos.

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

El dashboard solo ofrece la acción para archivos JSONL Codex directos que sigan
cumpliendo la política. `Preparar archivado` no mueve nada ni expone rutas;
`Confirmar archivado` envía la confirmación literal `ARCHIVE`. Al mover el
archivo se crea un recibo `.restore.json` en `archive_dir`. `GET /api/archives`
lo vuelve a mostrar en la cola tras una recarga y `Restaurar` devuelve el JSONL
a su ubicación original si sigue libre. Los ZIP de ChatGPT y los registros
Claude Code quedan fuera de esta acción web.

## Sesiones potencialmente bloqueadas

Una sesión Codex activa se señala únicamente si su último evento terminal es
`task_started`, no existe un cierre o aborto posterior y ha superado
`blocked_after_hours` sin actividad. Es una señal operativa para revisión
humana, no una afirmación semántica sobre el contenido de la conversación.
`Marcar como no bloqueada` exige una confirmación separada y solo guarda la
decisión local; no modifica ni mueve el JSONL. La señal permanece visible en la
lista de descartadas para poder reactivarla. Si cambia `last_activity_at`, el
descarte deja de aplicarse y una nueva coincidencia vuelve a requerir revisión.

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

La integración solo admite el Ollama de la máquina local: `127.0.0.1` en una
ejecución directa y `host.docker.internal` bajo Compose, siempre en el puerto
11434. No admite un endpoint remoto. La web declara si el servicio está listo,
no tiene modelos o no está disponible; nunca ejecuta `ollama pull`. Solo extrae
mensajes de usuario y asistente, limitados a los últimos 24.000 caracteres por
defecto. El resumen se renderiza en la ficha y no se guarda en SQLite.

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

El dashboard genera siempre un relevo base sin modelo. Incluye metadatos, el
objetivo conocido, el último resultado y cualquier petición posterior, cada
fragmento limitado a 800 caracteres. Declara lo que no puede inferir y nunca
incluye la ruta fuente. El Markdown se lee, copia o descarga desde la ficha.

El comando `handoff` conserva la síntesis semántica opcional mediante Ollama para
producir objetivo, trabajo completado, decisiones, pendientes, riesgos y primera
acción. No concatena la transcripción original ni modifica la sesión fuente.

```powershell
python -m zar_agent_session_ops handoff SESSION_ID --model qwen3:8b --output session-handoff.md
```

Para Codex, inicia una tarea nueva con `/new` y adjunta o pega
`session-handoff.md`. Para ChatGPT, abre un chat nuevo y adjunta el mismo archivo.
No uses `codex fork` para este caso: crea otro chat, pero conserva la
transcripción original completa en vez de reducir el contexto.

## Seguridad y privacidad

- El escaneo, los informes y la vista previa nunca modifican los JSON o JSONL
  originales.
- La base propia contiene metadatos, no transcripciones.
- Las conversaciones ChatGPT permanecen dentro del ZIP o JSON original.
- En la importación web, la copia gestionada permanece en el almacenamiento
  local de la aplicación; SQLite conserva solo sus metadatos.
- Los registros JSON de Claude Code solo se leen y no se copian como
  transcripciones.
- El proyecto no consulta las bases SQLite internas de Codex.
- La API se liga a loopback y omite las rutas de archivos fuente. El refresco
  reescribe solo el índice propio; archivar requiere una sesión aún elegible y
  la confirmación literal `ARCHIVE`.
- La integración GitHub solo envía identificadores explícitos a `api.github.com`.
- `--apply` es obligatorio para mover archivos.
- `maintain` tampoco mueve archivos sin `--apply-policy`.
- El mantenimiento web no acepta un modo de aplicación: es siempre `dry_run`.
- El relevo base del dashboard no sale de la API local. Los resúmenes, relevos
  CLI enriquecidos e informes operativos solo se envían al Ollama local.
- La API valida el endpoint Ollama contra una lista cerrada de hosts locales y
  solo acepta para resumir modelos anunciados por la instancia instalada.
- La ficha de actividad se calcula bajo demanda, limita cada fragmento a 500
  caracteres y no guarda su contenido en SQLite.
- En Compose, Claude Code se monta como solo lectura. Codex se monta con escritura
  para ejecutar únicamente el archivado confirmado y su restauración; la API se
  ejecuta con UID 10001 y solo el dashboard publica un puerto ligado a
  `127.0.0.1`.

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
