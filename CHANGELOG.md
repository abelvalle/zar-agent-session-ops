# Changelog

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
