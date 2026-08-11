# Changelog

## 0.26.0 - Complete decision flow / Flujo completo de decisión

- ES: reúne en la ficha tres pasos explícitos: revisar metadatos y señales,
  entender la actividad reciente y decidir con una razón visible.
- EN: brings three explicit steps into the record: review metadata and signals,
  understand recent activity, and decide with a visible reason.
- ES: permite preparar continuidad, descartar un falso bloqueo o revisar el
  archivado desde el mismo flujo; las confirmaciones existentes siguen vigentes.
- EN: prepares continuation, dismisses a false block, or reviews archiving from
  the same flow; existing confirmations remain in force.
- Verificación / Verification: 25 pruebas Python, 7 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.26 validados.
- Detalles / Details: [docs/milestones/0.26.0.md](docs/milestones/0.26.0.md).

## 0.25.0 - Actionable activity record / Ficha de actividad accionable

- ES: añade a cada ficha el objetivo, último resultado, petición pendiente,
  actividad reciente y siguiente paso derivados de evidencia local explícita.
- EN: adds objective, latest outcome, pending request, recent activity, and next
  step to every record from explicit local evidence.
- ES: incorpora `GET /api/sessions/{record_key}/activity`; limita la vista a seis
  fragmentos de 500 caracteres, no expone rutas y no persiste mensajes.
- EN: adds `GET /api/sessions/{record_key}/activity`; it caps the view at six
  500-character excerpts, exposes no paths, and persists no messages.
- Verificación / Verification: 25 pruebas Python, 7 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.25 validados.
- Detalles / Details: [docs/milestones/0.25.0.md](docs/milestones/0.25.0.md).

## 0.24.0 - Live local Codex limit / Límite local vigente de Codex

- ES: separa el límite Codex vigente del histórico de tokens y lo obtiene del
  último evento local válido sin reindexar el inventario completo.
- EN: separates the current Codex limit from historical tokens and reads it from
  the latest valid local event without reindexing the full inventory.
- ES: muestra hora observada, antigüedad y aviso tras 15 minutos sin una
  instantánea nueva; `Actualizar` consulta primero este dato ligero.
- EN: shows observation time, age, and a warning after 15 minutes without a new
  snapshot; `Refresh` checks this lightweight value first.
- ES: añade `GET /api/usage` sin rutas fuente ni contenido de conversación.
- EN: adds `GET /api/usage` without source paths or conversation content.
- Verificación / Verification: 24 pruebas Python, 7 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.24 validados.
- Detalles / Details: [docs/milestones/0.24.0.md](docs/milestones/0.24.0.md).

## 0.23.0 - Operational session search / Búsqueda operativa de sesiones

- ES: busca al instante entre las sesiones cargadas por título, repositorio,
  identificador, agente u origen.
- EN: instantly searches loaded sessions by title, repository, identifier,
  agent, or origin.
- ES: combina la consulta con agente, estado y paginación; cada cambio vuelve a
  la primera página y muestra el total filtrado.
- EN: combines the query with agent, status, and pagination; every change
  returns to the first page and shows the filtered total.
- ES: conserva `Localizar` como acción fiable, limpiando una búsqueda que
  impediría mostrar la fila exacta.
- EN: keeps `Locate` reliable by clearing a query that would hide the exact row.
- Verificación / Verification: 21 pruebas Python, 7 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.23 validados.
- Detalles / Details: [docs/milestones/0.23.0.md](docs/milestones/0.23.0.md).

## 0.22.0 - Visible model-free handoff / Relevo visible sin modelo

- ES: genera un relevo Markdown base desde la ficha sin exigir Ollama, llamadas
  externas ni persistencia de conversación.
- EN: generates a base Markdown handoff from the record without requiring
  Ollama, external calls, or conversation persistence.
- ES: renderiza el relevo dentro de la interfaz y ofrece copia y descarga con
  fragmentos recientes acotados y escapados.
- EN: renders the handoff inside the interface and provides copy and download
  actions with bounded, escaped recent excerpts.
- ES: mantiene el `handoff --model` CLI como síntesis Ollama opcional y declara
  de forma explícita los límites del modo base.
- EN: keeps CLI `handoff --model` as optional Ollama synthesis and explicitly
  states the limits of base mode.
- Verificación / Verification: 21 pruebas Python, 7 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.22 validados.
- Detalles / Details: [docs/milestones/0.22.0.md](docs/milestones/0.22.0.md).

## 0.21.0 - Reversible false-block dismissal / Descarte reversible de falsos bloqueos

- ES: convierte cada posible bloqueo en una revisión desde la ficha y exige la
  confirmación literal `NOT_BLOCKED` antes de ocultar la señal.
- EN: turns each potentially blocked signal into a record review and requires
  literal `NOT_BLOCKED` confirmation before hiding it.
- ES: conserva descartes en SQLite, permite reactivarlos y los invalida cuando
  la sesión registra nueva actividad.
- EN: persists dismissals in SQLite, restores them on demand, and invalidates
  them when the session records new activity.
- ES: mantiene cola e informe de bloqueos coherentes sin modificar ni mover los
  archivos de sesión.
- EN: keeps the blocked queue and report consistent without changing or moving
  session files.
- Verificación / Verification: 20 pruebas Python, 7 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.21 validados.
- Detalles / Details: [docs/milestones/0.21.0.md](docs/milestones/0.21.0.md).

## 0.20.0 - Confirmed reversible archiving / Archivado reversible confirmado

- ES: convierte cada candidata Codex directa en un flujo progresivo de
  previsualización, confirmación literal y archivado desde la ficha operativa.
- EN: turns each direct Codex candidate into a progressive preview, literal
  confirmation, and archive flow from the operational record.
- ES: crea recibos persistentes sin exponer rutas y muestra recuperaciones
  disponibles en la cola incluso después de recargar el dashboard.
- EN: creates persistent receipts without exposing paths and shows available
  recoveries in the queue even after the dashboard is reloaded.
- ES: añade claves opacas por registro para actuar sobre la sesión exacta aunque
  existan identificadores repetidos.
- EN: adds opaque per-record keys so actions target the exact session even when
  identifiers are duplicated.
- Verificación / Verification: 19 pruebas Python, 6 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.20 validados.
- Detalles / Details: [docs/milestones/0.20.0.md](docs/milestones/0.20.0.md).

## 0.19.0 - Session insight and usage / Diagnóstico y consumo de sesiones

- ES: renderiza los informes Markdown como HTML legible dentro del dashboard y
  conserva la descarga como acción secundaria.
- EN: renders Markdown reports as readable HTML inside the dashboard and keeps
  download as a secondary action.
- ES: `Localizar` enfoca y resalta la fila exacta incluso cuando el identificador
  aparece en varios registros.
- EN: `Locate` focuses and highlights the exact row even when an identifier
  appears in multiple records.
- ES: sustituye la consulta GitHub aislada por una ficha operativa con metadatos,
  consumo de tokens y relaciones GitHub.
- EN: replaces the isolated GitHub lookup with an operational record containing
  metadata, token usage, and GitHub relationships.
- ES: extrae contadores `token_count`, muestra consumo histórico por sesión y la
  última ventana Codex observada sin inventar una cuota fija de suscripción.
- EN: extracts `token_count` counters, shows historical usage per session and the
  latest observed Codex window without inventing a fixed subscription allowance.
- Verificación / Verification: 17 pruebas Python, 5 pruebas Angular, build de
  producción, auditoría npm, detector de interfaz y stack Docker 0.19 validados.
- Detalles / Details: [docs/milestones/0.19.0.md](docs/milestones/0.19.0.md).

## 0.18.0 - Inline Markdown reports / Informes Markdown integrados

- ES: añade un lector dentro del dashboard para consultar los informes semanal,
  bloqueos e inventario sin descargar archivos ni abandonar la aplicación.
- EN: adds an in-dashboard reader for weekly, blocked, and inventory reports
  without downloading files or leaving the application.
- ES: conserva la descarga del informe seleccionado como acción secundaria e
  incorpora estados de carga, error y reintento independientes.
- EN: keeps download for the selected report as a secondary action and adds
  independent loading, error, and retry states.
- Verificación / Verification: 17 pruebas Python, 5 pruebas Angular, build de
  producción, auditoría npm y stack Docker 0.18 validados.
- Detalles / Details: [docs/milestones/0.18.0.md](docs/milestones/0.18.0.md).

## 0.17.0 - Operational dashboard / Dashboard operativo

- ES: sustituye la pantalla centrada en el inventario por una cola de atención
  que muestra bloqueos y retención antes de la tabla y permite localizar cada
  sesión señalada.
- EN: replaces the inventory-first screen with an attention queue that shows
  blocked and retention signals before the table and locates each flagged
  session.
- ES: reutiliza metadatos de JSONL Codex sin cambios y muestra duración,
  registros cambiados y reutilizados tras cada actualización.
- EN: reuses metadata for unchanged Codex JSONL files and reports duration,
  changed records, and reused records after each refresh.
- Verificación / Verification: 17 pruebas Python, 4 pruebas Angular, build de
  producción, auditoría npm y stack Docker 0.17 validados.
- Detalles / Details: [docs/milestones/0.17.0.md](docs/milestones/0.17.0.md).

## 0.16.0 - Retention preview / Vista previa de retención

- ES: añade `GET /api/retention` con el umbral configurado y las sesiones
  activas que cumplirían la política, sin exponer `archive_dir`.
- EN: adds `GET /api/retention` with the configured threshold and active
  sessions that match policy, without exposing `archive_dir`.
- ES: muestra candidatas y estado vacío en el dashboard; la web no incorpora
  ninguna acción de archivado ni modifica archivos.
- EN: shows candidates and the empty state in the dashboard; the web adds no
  archive action and modifies no files.
- Verificación / Verification: 16 pruebas Python, 3 pruebas Angular, build de
  producción, auditoría npm y stack Docker 0.16 validados.
- Detalles / Details: [docs/milestones/0.16.0.md](docs/milestones/0.16.0.md).

## 0.15.0 - Claude Code session registry / Registro de sesiones Claude Code

- ES: añade un adaptador conservador para `CLAUDE_HOME/sessions/*.json` que
  normaliza identificador, proyecto, versión, tipo y punto de entrada.
- EN: adds a conservative adapter for `CLAUDE_HOME/sessions/*.json`, normalizing
  identifier, project, version, kind, and entrypoint.
- ES: integra Claude Code en `scan`, `maintain`, refresco API, Docker Compose y
  filtros del dashboard con estado explícito `registered`.
- EN: integrates Claude Code into `scan`, `maintain`, API refresh, Docker
  Compose, and dashboard filters with the explicit `registered` status.
- Verificación / Verification: 16 pruebas Python, 3 pruebas Angular, build de
  producción, auditoría npm, 478 sesiones Codex y 2 registros Claude reales.
- Detalles / Details: [docs/milestones/0.15.0.md](docs/milestones/0.15.0.md).

## 0.14.0 - Dashboard Markdown exports / Exportaciones Markdown del dashboard

- ES: expone inventario, actividad semanal y posibles bloqueos como descargas
  `text/markdown` con nombres de archivo definidos por la API local.
- EN: exposes inventory, weekly activity, and blocked signals as `text/markdown`
  downloads with filenames defined by the local API.
- ES: añade tres acciones accesibles al dashboard mediante enlaces nativos; no
  incorpora estado, dependencias ni acceso a transcripciones.
- EN: adds three accessible dashboard actions through native links, with no new
  state, dependencies, or transcript access.
- Verificación / Verification: 14 pruebas Python, 3 pruebas Angular, build de
  producción, auditoría npm y stack Docker 0.14 validados.
- Detalles / Details: [docs/milestones/0.14.0.md](docs/milestones/0.14.0.md).

## 0.13.0 - Weekly operational digest / Informe operativo semanal

- ES: añade `weekly-digest` para consolidar trabajo, decisiones técnicas,
  pendientes, riesgos y commits o Pull Requests explícitos mediante Ollama local.
- EN: adds `weekly-digest` to consolidate work, technical decisions, pending
  tasks, risks, and explicit commits or Pull Requests through local Ollama.
- ES: limita la entrada a siete días, 12 sesiones recientes y 24.000 caracteres;
  `maintain --model` genera el mismo informe dentro del ciclo programable.
- EN: bounds input to seven days, 12 recent sessions, and 24,000 characters;
  `maintain --model` generates the same report in the schedulable cycle.
- Verificación / Verification: 14 pruebas Python, 3 pruebas Angular, build de
  producción, auditoría npm y stack Docker 0.13 validados.
- Detalles / Details: [docs/milestones/0.13.0.md](docs/milestones/0.13.0.md).

## 0.12.0 - Minimal-context handoff / Relevo de contexto mínimo

- ES: añade `handoff` para convertir una sesión Codex o ChatGPT indexada en un
  relevo Markdown conciso mediante el Ollama local.
- EN: adds `handoff` to turn an indexed Codex or ChatGPT session into a concise
  Markdown handoff through local Ollama.
- ES: conserva solo metadatos mínimos, objetivo, trabajo, decisiones,
  pendientes, riesgos y siguiente acción; no concatena la transcripción original.
- EN: retains only minimal metadata, goal, work, decisions, pending tasks,
  risks, and next action; it does not append the raw transcript.
- Verificación / Verification: 13 pruebas Python, 3 pruebas Angular, build de
  producción y stack Docker 0.12 validados.
- Detalles / Details: [docs/milestones/0.12.0.md](docs/milestones/0.12.0.md).

## 0.11.0 - Background inventory refresh / Actualización en segundo plano

- ES: añade `POST /api/refresh` y `GET /api/refresh` para iniciar un escaneo
  Codex no bloqueante y consultar su estado.
- EN: adds `POST /api/refresh` and `GET /api/refresh` to start a non-blocking
  Codex scan and query its state.
- ES: el dashboard inicia el escaneo, muestra progreso y resultado, recarga el
  inventario al terminar y evita solicitudes duplicadas.
- EN: the dashboard starts the scan, displays progress and result, reloads the
  inventory on completion, and prevents duplicate requests.
- Verificación / Verification: 12 pruebas Python, 3 pruebas Angular, refresco
  real de 461 sesiones con API disponible y stack Docker 0.11 validado.
- Detalles / Details: [docs/milestones/0.11.0.md](docs/milestones/0.11.0.md).

## 0.10.0 - Local Docker stack / Stack Docker local

- ES: empaqueta la API y el dashboard en imágenes multi-stage reproducibles,
  fijadas por versión y digest, y las coordina con Docker Compose.
- EN: packages the API and dashboard in reproducible multi-stage images pinned
  by version and digest, coordinated through Docker Compose.
- ES: monta Codex en solo lectura, conserva SQLite en un volumen, ejecuta la API
  sin privilegios y publica únicamente el dashboard en loopback.
- EN: mounts Codex read-only, persists SQLite in a volume, runs the API without
  privileges, and publishes only the dashboard on loopback.
- Verificación / Verification: 11 pruebas Python, 2 pruebas Angular, auditoría
  npm sin vulnerabilidades, build de ambas imágenes y arranque limpio sobre 461
  sesiones en 153 segundos.
- Detalles / Details: [docs/milestones/0.10.0.md](docs/milestones/0.10.0.md).

## 0.9.0 - GitHub relationships / Relaciones con GitHub

- ES: detecta enlaces explícitos a Issues, Pull Requests y commits en sesiones
  Codex o ChatGPT y resuelve título y estado mediante la API REST de GitHub.
- EN: detects explicit Issue, Pull Request, and commit links in Codex or ChatGPT
  sessions and resolves title and state through GitHub's REST API.
- ES: añade el comando `github`, un endpoint por sesión y consulta bajo demanda
  desde el dashboard; `GITHUB_TOKEN` es opcional y nunca se persiste.
- EN: adds the `github` command, a per-session endpoint, and on-demand dashboard
  lookup; `GITHUB_TOKEN` is optional and never persisted.
- Verificación / Verification: 11 pruebas Python, 2 pruebas Angular, build de
  producción y ejecución real sobre 461 sesiones con 8 commits resueltos.
- Detalles / Details: [docs/milestones/0.9.0.md](docs/milestones/0.9.0.md).

## 0.8.0 - Local Angular dashboard / Dashboard Angular local

- ES: añade un dashboard Angular 22 y Material con métricas, filtros,
  paginación, revisión de bloqueos y diseño adaptable.
- EN: adds an Angular 22 and Material dashboard with metrics, filters,
  pagination, blocked-session review, and responsive layout.
- ES: establece `/api/health`, `/api/sessions` y `/api/blocked` como rutas
  canónicas; mantiene las rutas 0.7 ocultas del esquema por compatibilidad.
- EN: makes `/api/health`, `/api/sessions`, and `/api/blocked` canonical while
  retaining the 0.7 routes outside the schema for compatibility.
- Verificación / Verification: 7 pruebas Python, 2 pruebas Angular, auditoría
  npm sin vulnerabilidades, build de producción y ejecución real sobre 461
  sesiones en escritorio y móvil.
- Detalles / Details: [docs/milestones/0.8.0.md](docs/milestones/0.8.0.md).

## 0.7.0 - Local read-only API / API local de solo lectura

- ES: añade una API FastAPI local con salud, inventario filtrable y posibles
  bloqueos; no expone rutas de archivos ni operaciones de escritura.
- EN: adds a local FastAPI API for health, filtered inventory, and blocked
  signals; it exposes neither file paths nor write operations.
- ES: incorpora `serve`, ligado exclusivamente a `127.0.0.1`, y documentación
  OpenAPI generada por FastAPI.
- EN: adds `serve`, bound exclusively to `127.0.0.1`, plus FastAPI-generated
  OpenAPI documentation.
- Verificación / Verification: 7 pruebas; API real sobre 461 sesiones, 3 rutas
  OpenAPI, 1 posible bloqueo y 0 fuentes modificadas.
- Detalles / Details: [docs/milestones/0.7.0.md](docs/milestones/0.7.0.md).

## 0.6.0 - Blocked-session signals and maintenance / Señales de bloqueo y mantenimiento

- ES: detecta de forma conservadora sesiones Codex potencialmente bloqueadas y
  genera un informe específico para revisión humana.
- EN: conservatively detects potentially blocked Codex sessions and produces a
  dedicated report for human review.
- ES: añade `maintain`, un ciclo único apto para el Programador de tareas o
  `cron`; la política de archivo sigue siendo una simulación por defecto.
- EN: adds `maintain`, a one-shot cycle for Task Scheduler or `cron`; archive
  policy actions remain a dry run by default.
- Verificación / Verification: 6 pruebas; ejecución real sobre 461 sesiones,
  con 1 posible bloqueo, 16 candidatas a archivo y 0 fuentes modificadas.
- Detalles / Details: [docs/milestones/0.6.0.md](docs/milestones/0.6.0.md).

## 0.5.0 - ChatGPT export import / Importación de exportaciones ChatGPT

- ES: importa ZIP, JSON únicos y exportaciones numeradas; conserva únicamente
  metadatos y permite resumir una conversación desde su archivo original.
- EN: imports ZIP, single JSON, and numbered exports; stores metadata only and
  can summarize a conversation from its original source file.
- Verificación / Verification: 5 pruebas con un ZIP sintético de dos
  conversaciones y migración preservando registros Codex `0.4.x`.
- Límite / Limit: el esquema interno de `conversations.json` no está publicado;
  el adaptador es experimental y no se validó contra una exportación personal.
- Detalles / Details: [docs/milestones/0.5.0.md](docs/milestones/0.5.0.md).

## 0.4.0 - Codex inventory / Inventario Codex

- ES: incorpora sesiones activas y archivadas, nombres de tarea, origen y tipo
  de hilo; migra automáticamente la base `0.3.x`.
- EN: adds active and archived sessions, task names, origin, and thread source;
  automatically migrates the `0.3.x` database.
- Verificación / Verification: 4 pruebas; inventario real de 58 sesiones
  activas, 403 archivadas y 416 nombres indexados.
- Detalles / Details: [docs/milestones/0.4.0.md](docs/milestones/0.4.0.md).

## 0.3.0 - Weekly reports and Ollama

- Informes semanales y resúmenes locales acotados mediante Ollama.
- Weekly reports and bounded local summaries through Ollama.

## 0.2.0 - Retention policies

- Políticas TOML y archivado por lotes con simulación predeterminada.
- TOML policies and batch archiving with dry-run defaults.

## 0.1.0 - Codex metadata MVP

- Escaneo JSONL, SQLite, informes Markdown y archivado individual.
- JSONL scanning, SQLite, Markdown reports, and individual archiving.
