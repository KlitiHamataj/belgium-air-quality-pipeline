# Belgium Air Quality Pipeline -- documentation

ELT pipeline for Belgian air quality (IRCELINE + Open-Meteo → dbt/DuckDB → Streamlit), refreshed daily on GitHub Actions.

This directory is a wiki maintained by an LLM: linked markdown pages, nothing outside the
repository. The rules are in [`CLAUDE.md`](CLAUDE.md).

## Start here

This wiki grows as work touches new areas. So far:

1. [[daily-refresh]] -- how the live dashboard gets fresh data every day, and its traps

---

## concepts


## architecture


## subsystems


## decisions


## reference


## operations

- [[daily-refresh]] -- scheduled GitHub Actions run, release-asset publishing, dashboard download

## history


---

## Using this wiki

```
/docs-sync     right after a deploy or release -- reads only what changed since verified_at
/docs-lint     integrity check (orphans, broken links, broken sources, stale, unverified)
/docs-query    ask the docs. If it is not there, the answer says so
/docs-status   commits not yet reflected, stale pages, recent work
```

Every page carries `verified_at`, the commit it was checked against. Change code, run
`/docs-sync`.
