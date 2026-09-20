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
- The Dockerfile and run.sh have not been build/run-tested -- no Docker
  runtime is available in this development environment either (checked:
  `docker` is not installed here). Before relying on them: run
  `docker build .` inside `enderata/` **on a machine with Docker** and
  fix whatever the geopandas/GDAL compilation step surfaces -- that is
  the most likely failure point, followed by the Postgres init sequence
  in run.sh.
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
- `repository.yaml` and `config.yaml` contain placeholder URLs
  (`<your-org>`) -- replace before publishing anywhere.

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
2. On a machine with Docker: build-test the Dockerfile and fix the
   GDAL/geopandas install step; run-test run.sh's Postgres init/start
   sequence. Not possible in this development environment (no Docker
   here).
3. Wire real ingestion in: have `number-district` (or a new command)
   call `ingestion/open_buildings.py` and `ingestion/osm_streets.py`
   instead of reading pre-made GeoJSON, and call
   `ingestion/load_postgis.py` to persist results.
4. Re-run the permanence test (`tests/integration/`) against the real
   Huambo extract once ingestion is wired in, not just the fixture.
5. Replace the in-memory sorted-building-id sequencing in `pipeline.py`
   with a persistent DB sequence keyed by building_id, so IDs survive
   new buildings being added later without shifting existing ones.
