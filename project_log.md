# ENDERETA — Project Log

**Read this first.** One page, tables only, no narrative — a running
index of what needs your decision and what's known-broken, so you can
scan it before opening `discrepancies.md` (full technical detail per
item) or the current `dayX_objectives.md` (session-by-session task
tracking). Updated every time a new decision or issue surfaces;
resolved rows move to the bottom "Resolved" table with the answer, not
deleted.

**Reading order:** this file → `discrepancies.md` → `dayX_objectives.md` → `agreed-workflow.md`.

This project also follows ECC's plan-first, confirm-before-code
workflow (see `agreed-workflow.md`) — this doc set adds cross-session
continuity on top of that, it doesn't replace it.

---

## Decisions needed from you

| # | Decision | One-line context | Full detail |
|---|---|---|---|
| 1 | Compliant basemap for the viewer | OSM's own tiles are policy-blocked for a packaged app (403 confirmed on real HA run); viewer currently has no basemap, just auto-fit GeoJSON on a plain background | `discrepancies.md` § Compliant basemap |
| 2 | Real Huambo district AOI polygon | Everything built/tested so far (pipeline, CLI, viewer) runs only on a 5-building synthetic fixture, not real Huambo data | `discrepancies.md` § Real Huambo AOI boundary |
| 3 | Persistent postal-ID sequencing design | `pipeline.py` currently sequences IDs by sorting building_id in memory — fine for a closed fixture, not for a growing real dataset | `discrepancies.md` § Persistent postal-ID sequencing |

## Known issues (not decisions — being investigated, no action needed from you yet)

| # | Issue | Status |
|---|---|---|
| 1 | Ingestion modules (`open_buildings.py`, `osm_streets.py`) not wired into the CLI | Structurally complete, never exercised against real data or network; `number-district` currently consumes pre-made GeoJSON only |
| 2 | No PostGIS write step in the CLI | `ingestion/load_postgis.py` exists but nothing calls it yet — `number-district` only writes GeoJSON/CSV |
| 3 | No Alembic migrations | Schema created via `Base.metadata.create_all()`; fine for the POC, will need real migrations before the schema can evolve against live data |

## Resolved

| # | Issue | Resolution |
|---|---|---|
| 1 | HA Supervisor build failed: `apt-get: not found` | `build.yaml`'s image name didn't match Supervisor's validation regex, silently fell back to HA's Alpine base. Removed `build.yaml`, hardcoded `FROM python:3.12-slim-bookworm` in the Dockerfile — fixed in add-on v0.1.1 |
| 2 | `bashio` install step 404'd | URL no longer resolves, and nothing in the codebase actually called bashio — removed it; add-on options now read from `/data/options.json` via `jq` — fixed in v0.1.1 |
| 3 | `pg_ctl` failed: "Permission denied" writing `/data/postgres.log` | `/data` is root-owned, only `/data/postgres` was chowned to `postgres`; log now writes inside `${PGDATA}`, `/var/run/postgresql` pre-created for the unix socket — fixed in v0.1.1 |
| 4 | `CREATE EXTENSION postgis` failed: extension not available | Debian's plain `postgis` apt package is client-tools-only; the server extension needs the versioned `postgresql-15-postgis-3` package, now installed alongside it — fixed in v0.1.3 |
| 5 | Every basemap tile 403'd | OpenStreetMap's tile usage policy forbids `tile.openstreetmap.org` in a distributed/packaged app without prior OSMF approval — tile layer removed, viewer auto-fits to GeoJSON on a plain background instead (see open decision #1 above for a real basemap) — fixed in v0.1.4 |
| 6 | Confidential business-plan PDF risk on a public repo | `ENDERETA_Business_Plan.pdf` (marked "Confidential — Not for distribution") kept local-only, added to `.gitignore` before the first push |
| 7 | Personal screenshot accidentally committed to the public repo | A `git add -A` swept up a screenshot containing browser tabs/local IP; untracked, history rewritten with `git filter-branch`, and force-pushed after explicit user confirmation |
| 8 | Add-on had no icon/logo | Generated a navy map-pin mark with a teal accent (Pillow, programmatic — not a guessed/downloaded asset); `icon.png` + `logo.png` added in v0.1.2 |
