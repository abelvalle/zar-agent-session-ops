# Changelog

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
