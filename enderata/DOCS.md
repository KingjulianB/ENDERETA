# ENDERETA add-on

Geospatial data pipeline and permanent postal-ID numbering engine for the
ENDERETA POC (Huambo district), packaged as a Home Assistant add-on so it
can run on infrastructure you already operate, before any dedicated
government-grade hosting exists.

## What this add-on does today

- Runs a bundled PostgreSQL + PostGIS instance (data persisted under
  `/data/postgres`, on Home Assistant's per-addon storage) -- **not**
  run-tested (see below).
- Serves a Leaflet demo viewer through HA ingress, reading GeoJSON layers
  from `/data/export`.
- Ships the `enderata` Python package: postal-ID generation, street
  assignment, house-numbering and the `pipeline.py` orchestration that
  ties them together, plus ingestion modules for Google Open Buildings
  and OpenStreetMap (structurally complete, not yet exercised against
  real data).
- `enderata number-district --buildings ... --streets ... --out ...`
  runs the real pipeline end to end on already-ingested GeoJSON and
  writes a numbered `buildings.geojson` + `addresses.csv`. Verified by
  hand against `tests/fixtures/synthetic_sample/` (5 fake buildings, 2
  fake streets) -- output confirmed correct (valid check digits, no
  duplicate IDs, address never contains the postal ID).
- 16/16 automated tests pass, including an integration test that reruns
  the pipeline twice on the fixture and asserts identical postal IDs
  (the permanence guarantee) -- see `tests/integration/`.

## What is NOT done yet -- do not assume otherwise

- Ingestion is not wired into the CLI: `number-district` consumes
  already-ingested GeoJSON, it does not call `ingestion/open_buildings.py`
  or `ingestion/osm_streets.py` itself. Those two modules are still
  unexercised against real data or network.
- The Dockerfile now builds past the apt-get/system-deps step (fixed
  2026-09-20: `build.yaml` was silently rejected by Supervisor's
  validation, which fell back to HA's own Alpine base image and broke
  `apt-get`; fixed by hardcoding `FROM python:3.12-slim-bookworm`
  directly and removing `build.yaml`) and past the bashio install step
  (removed 2026-09-20: it was dead weight -- nothing in the codebase
  actually called bashio, and its install URL 404s. Add-on options are
  now read directly from `/data/options.json` via `jq` in `run.sh`
  instead, matching `config.yaml`'s `schema:`). `pip install -r requirements.txt` (geopandas/osmnx) and the full Docker
  build now succeed on a real HA install. `initdb` runs fine at
  container start; `pg_ctl start` initially failed ("Permission denied"
  writing the log to `/data/postgres.log`, since `/data` itself is
  root-owned) -- fixed 2026-09-20 by logging inside `${PGDATA}` instead
  and pre-creating `/var/run/postgresql` for the unix socket. Whether
  Postgres actually accepts connections and the viewer server starts is
  still unverified -- report the next error and it'll get fixed the
  same way.
- No PostGIS write step in the CLI yet (`ingestion/load_postgis.py`
  exists but nothing calls it) -- `number-district` only produces
  GeoJSON/CSV files, it does not touch the database.
- No Alembic migrations: schema is created with
  `Base.metadata.create_all()`, fine for a POC, not for evolving a live
  dataset.
- The Huambo district AOI boundary and Open Buildings tile list are not
  included -- you need to supply the district polygon before real
  ingestion can run. Everything verified so far used a 5-building
  synthetic fixture, NOT real Huambo data.
- `pipeline.py` sequences postal IDs by sorting building IDs in memory
  (documented in its docstring) -- valid only for a fixed, closed input
  set. A persistent DB sequence is required before this can run against
  a growing real dataset.
- `repository.yaml` and `config.yaml` now point at the real repo
  (`https://github.com/KingjulianB/ENDERETA`).

## Installing as a local add-on

1. In Home Assistant: Settings -> Add-ons -> Add-on Store -> the
   three-dot menu -> Repositories, and add the path/URL to this repo
   (the folder containing `repository.yaml`).
2. The "ENDERETA" add-on should appear in the store; install and start
   it. Ingress exposes the demo viewer in the HA sidebar.

## Configuration (config.yaml options)

| Option | Purpose |
|---|---|
| `country_code` | 2-letter prefix for postal IDs (default `AO`) |
| `district_code` | 3-letter district prefix (default `HUA` for Huambo) |
| `aoi_district` | machine name used by ingestion scripts |

## Running the tests locally (no Docker needed)

```bash
cd enderata
pip install -r requirements.txt pytest   # geopandas needed for the integration tests
pytest
```

Unit tests cover postal-ID generation/validation (including the
check-digit catching a transposed-digit transcription error),
street-side assignment and house-number ordering. Integration tests run
the full `pipeline.py` against the synthetic fixture and assert
permanence + ID/address separation. Neither covers the ingestion
modules (need real geodata and network access) or the Docker/Postgres
startup path.

You can also run the CLI directly against the fixture:

```bash
PYTHONPATH=src python -m enderata.cli number-district \
  --buildings tests/fixtures/synthetic_sample/buildings.geojson \
  --streets tests/fixtures/synthetic_sample/streets.geojson \
  --out .demo_export --country AO --district HUA
```

## Next steps toward the Foundation / Core-engine milestones

1. Supply the real Huambo district AOI polygon (everything so far has
   run only on the 5-building synthetic fixture).
2. Keep iterating the build on real HA Supervisor output: next likely
   failure points are `pip install` compiling geopandas/osmnx, and
   run.sh's Postgres init/start sequence (untested beyond `apt-get
   install postgresql...` succeeding at image-build time).
3. Wire real ingestion in: have `number-district` (or a new command)
   call `ingestion/open_buildings.py` and `ingestion/osm_streets.py`
   instead of reading pre-made GeoJSON, and call
   `ingestion/load_postgis.py` to persist results.
4. Re-run the permanence test (`tests/integration/`) against the real
   Huambo extract once ingestion is wired in, not just the fixture.
5. Replace the in-memory sorted-building-id sequencing in `pipeline.py`
   with a persistent DB sequence keyed by building_id, so IDs survive
   new buildings being added later without shifting existing ones.
