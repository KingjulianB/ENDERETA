# ENDERETA add-on

Geospatial data pipeline and permanent postal-ID numbering engine for the
ENDERETA POC (Luanda district -- pilot changed from Huambo 2026-09-22,
see `discrepancies.md`), packaged as a Home Assistant add-on so it
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
- 33/33 automated tests pass, including an integration test that reruns
  the pipeline twice on the fixture and asserts identical postal IDs
  (the permanence guarantee) -- see `tests/integration/`.
- The viewer now has a real self-hosted basemap: `tiles/luanda.mbtiles`
  (OpenMapTiles vector tiles, generated offline with Planetiler --
  see `tiles/README.md`) served at `GET /tiles/<z>/<x>/<y>.pbf` and
  rendered client-side with Leaflet.VectorGrid. No third-party tile
  host, no usage-policy risk (unlike the earlier OSM-tile 403). Roads,
  buildings, water and landuse render; road/place text labels don't
  (VectorGrid renders geometry, not label placement -- a known,
  accepted limitation for now). Verified in a real browser
  (chrome-devtools screenshots), not just Python tests.
- `enderata satellite-builtup` (CLI) and `POST /api/load-satellite`
  (viewer button "Load satellite layer") fetch a real, current
  Sentinel-2 scene over Luanda (public AWS STAC catalog, free, no API
  key, confirmed commercial-use-safe) and render a coarse built-up-area
  layer -- **not** building footprints, a density/extent signal only
  (10m/pixel). Requires outbound internet from wherever the add-on
  runs (new requirement -- every other feature works fully offline).
  The panel that appears after loading it lets you toggle the true-
  colour image and NDBI/NDVI heatmaps on top of the mask (georeferenced
  overlays, not static screenshots) and adjust the NDBI/NDVI thresholds
  with sliders + "Recompute" -- useful for visually judging the mask's
  quality and tuning it without a code change.
  See `enderata/src/enderata/satellite/` docstrings for what this can
  and can't do, and `discrepancies.md` § Sovereign building/road
  detection model for why (NICFI's license ruled it out; no budget yet
  for imagery precise enough for real building detection).
- `enderata estimate-addresses` (CLI) and `POST /api/estimate-addresses`
  (viewer button "Assign addresses (estimated)") chain three things
  into the real numbering pipeline: real OpenStreetMap streets (`enderata/
  src/enderata/ingestion/osm_streets.py`, fetched live via osmnx/Overpass
  -- verified against real Luanda data, 2305 street edges), estimated
  building points sampled on a grid inside the Sentinel-2 built-up mask
  (`enderata/src/enderata/satellite/building_estimate.py`, capped at
  1000 points by default -- `street_assignment.py`'s nearest-street
  search has no spatial index, so an uncapped grid over a real city-
  scale built-up area is too slow for an interactive button), and
  `pipeline.py::run_pipeline` (unchanged). Verified end-to-end against
  real Luanda data (999/999 estimated points addressed, ~20s) and in a
  real browser. **These building locations are ESTIMATES -- a coarse
  grid sample, not a real building-footprint detection result** -- see
  `discrepancies.md` § Real Luanda AOI boundary. Output is written to
  its own `estimated_buildings.geojson`/`estimated_streets.geojson`
  files so it never overwrites the demo fixture or gets visually
  confused with it (separate purple layer + on-screen disclaimer).

## What is NOT done yet -- do not assume otherwise

- `ingestion/osm_streets.py` is now wired in (via `estimate-addresses`,
  see above) and verified against real Luanda data. `ingestion/
  open_buildings.py` (Google Open Buildings) is still unwired and
  unexercised -- real building footprints for Luanda remain unavailable
  (see `discrepancies.md` § Sovereign building/road detection model);
  `estimate-addresses` uses grid-sampled points as a stand-in, not this
  module. `number-district` still consumes already-ingested GeoJSON
  directly, independent of either ingestion module.
- The Dockerfile now builds past the apt-get/system-deps step (fixed
  2026-09-20: `build.yaml` was silently rejected by Supervisor's
  validation, which fell back to HA's own Alpine base image and broke
  `apt-get`; fixed by hardcoding `FROM python:3.12-slim-bookworm`
  directly and removing `build.yaml`) and past the bashio install step
  (removed 2026-09-20: it was dead weight -- nothing in the codebase
  actually called bashio, and its install URL 404s. Add-on options are
  now read directly from `/data/options.json` via `jq` in `run.sh`
  instead, matching `config.yaml`'s `schema:`). `pip install -r requirements.txt` (geopandas/osmnx) and the full Docker
  build succeed on a real HA install. `initdb` and `pg_ctl start` both
  confirmed working on real hardware (the log-permission fix in 0.1.1
  is verified, not just theoretical). `CREATE EXTENSION postgis` then
  failed because the plain `postgis` apt package is client-tools-only
  on Debian -- fixed in 0.1.3 by also installing
  `postgresql-15-postgis-3`. Confirmed on 0.1.4: the add-on now starts
  fully and the demo viewer loads through HA ingress.
- The viewer's raster basemap (OpenStreetMap tiles) was removed in
  0.1.4 -- every tile 403'd because OSM's tile usage policy forbids
  using tile.openstreetmap.org from a distributed app without prior
  OSMF approval. The map now just renders on a plain background and
  auto-fits to the loaded GeoJSON. Picking a compliant basemap (a
  licensed provider, or self-hosted tiles) is unresolved -- see "Next
  steps".
- The viewer starts empty until something populates `/data/export`.
  Click the **"Load demo data"** button in the viewer itself (added in
  0.1.6) -- it calls `POST /api/load-demo`, which runs the pipeline
  against the bundled synthetic fixture server-side and reloads the
  map. This exists specifically because HA's standard "Terminal & SSH"
  add-on has no docker socket access (`docker: command not found` is
  the real error users hit trying `docker exec`), so a shell-based
  workflow isn't viable for most people -- everything needed for the
  demo must be reachable from the web UI.
- No PostGIS write step in the CLI yet (`ingestion/load_postgis.py`
  exists but nothing calls it) -- `number-district` only produces
  GeoJSON/CSV files, it does not touch the database.
- No Alembic migrations: schema is created with
  `Base.metadata.create_all()`, fine for a POC, not for evolving a live
  dataset.
- The Luanda district AOI boundary and Open Buildings tile list are not
  included -- you need to supply the district polygon before real
  ingestion can run. Everything verified so far used a 5-building
  synthetic fixture (near the old Huambo location -- see the fixture's
  own README), NOT real Luanda data.
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
| `district_code` | 3-letter district prefix (default `LUA` for Luanda) |
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
  --out .demo_export --country AO --district LUA
```

## Next steps toward the Foundation / Core-engine milestones

1. Supply the real Luanda district AOI polygon (everything so far has
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
   Luanda extract once ingestion is wired in, not just the fixture.
5. Replace the in-memory sorted-building-id sequencing in `pipeline.py`
   with a persistent DB sequence keyed by building_id, so IDs survive
   new buildings being added later without shifting existing ones.
