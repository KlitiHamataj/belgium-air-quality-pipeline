# Work log

Append-only. Newest entries at the bottom.

---

## [2026-11-11] setup | docs/ wiki scaffolded

- Categories: concepts - architecture - subsystems - decisions - reference - operations - history
- Baseline commit: `9b87f25`
- Created: `docs/{CLAUDE,index,log}.md`, `raw/`, 4 `.claude/commands/docs-*`,
  and `.claude/scripts/docs-lint.py`

- Started in grow mode. First page: `operations/daily-refresh.md`, written from
  `.github/workflows/daily-refresh.yml`, `src/dashboard/app.py` and the ingestion
  filename change made in the same session. No other areas documented yet.

## [2026-11-13] grow | Metabase page

- Added `operations/metabase.md` for the new optional local Metabase (compose profile
  `metabase`, `docker/Dockerfile.metabase`, `src/bi/snapshot.py`, DAG task
  `publish_metabase_snapshot`)
- Linked from `index.md`; added a row to the "When you change code" table in `CLAUDE.md`
