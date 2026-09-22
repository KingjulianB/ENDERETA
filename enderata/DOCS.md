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
- 55/55 automated tests pass, including an integration test that reruns
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
  Defaults to the real full Luanda AOI (`aoi.py`, added 0.1.22 -- was a
  fixed 1.6km radius before), verified end-to-end: 24,435 built-up
  polygons across the whole municipality, 17.8s. `read_bands`
  (`satellite/sentinel2.py`) now sizes its output raster to the bbox's
  real aspect ratio at ~10m/pixel (`_compute_out_shape`, capped at
  `max_dimension` pixels on the longer side) instead of forcing every
  bbox into a square -- fine for the old near-square test radius, would
  have badly distorted a ~15km x 18km AOI. This also fixed the root
  cause of `bounds_wgs84` previously coming back roughly double the
  requested bbox (an internally inconsistent native-resolution-transform
  + resampled-array-shape pairing) -- now matches to ~0.001°.
  See `enderata/src/enderata/satellite/` docstrings for what this can
  and can't do, and `discrepancies.md` § Sovereign building/road
  detection model for why (NICFI's license ruled it out; no budget yet
  for imagery precise enough for real building detection).
- `enderata estimate-addresses` (CLI) and `POST /api/estimate-addresses`
  (viewer button "Assign addresses (estimated)") chain three things
  into the real numbering pipeline: real OpenStreetMap streets (`enderata/
  src/enderata/ingestion/osm_streets.py`, fetched live via osmnx/Overpass
  -- verified against real Luanda data, 2305 street edges at the
  default 1.6km radius), estimated building points sampled on a grid
  inside the Sentinel-2 built-up mask (`enderata/src/enderata/satellite/
  building_estimate.py`, capped at 1000 points by default -- keeps the
  numbering pipeline's own cost bounded regardless of AOI size), and
  `pipeline.py::run_pipeline` (unchanged, but its nearest-street search
  now uses an STRtree spatial index -- see below). Verified end-to-end
  against real Luanda data (999/999 estimated points addressed, ~20s
  at 1.6km radius) and in a real browser. **These building locations
  are ESTIMATES -- a coarse grid sample, not a real building-footprint
  detection result** -- see `discrepancies.md` § Real Luanda AOI
  boundary. Output is written to its own `estimated_buildings.geojson`/
  `estimated_streets.geojson` files so it never overwrites the demo
  fixture or gets visually confused with it (separate purple layer +
  on-screen disclaimer).
- `numbering/street_assignment.py`'s nearest-street search uses an
  STRtree spatial index (`StreetIndex`, added 0.1.18) instead of a
  linear scan. Verified with a real 20km-radius Luanda extract (897
  estimated buildings x 268,753 real OSM streets, via `estimate-
  addresses` at a wider radius than the button's default): street
  assignment itself takes 1.2s, down from ~675s measured with the
  previous linear scan on the same input. At that radius the ~61s
  total run time is now almost entirely real Overpass (43.3s) and
  Sentinel-2 (14.1s) network fetch time, not computation.
- `enderata real-addresses` (CLI) and `POST /api/real-addresses`
  (viewer button "Assign addresses (real OSM buildings)") -- a second,
  preferred addressing path added 0.1.19: real OSM-mapped buildings
  (new `ingestion/osm_buildings.py`, `ox.features_from_bbox(bbox,
  tags={"building": True})`, polygon centroid or the point itself)
  instead of `estimate-addresses`' grid-sampled points. No satellite
  fetch at all -- faster (1.2s verified at 1.6km radius, vs ~20s) and
  the building locations are REAL, not estimated. Verified against real
  Luanda data: 749/749 real OSM-mapped buildings addressed, and in a
  real browser (distinct green layer). OSM's building coverage in
  Luanda is real but volunteer-mapped and incomplete -- not exhaustive
  like Google Open Buildings would be (see `discrepancies.md` §
  Sovereign building/road detection model; that dataset's own data is
  clearly licensed (CC-BY-4.0/ODbL) but its Source Cooperative hosting
  turned out to need non-trivial S3/GeoParquet plumbing to access
  reliably -- not wired in yet, a planned follow-up to fill gaps where
  OSM has no mapped buildings, not a replacement for this path).
  `estimate-addresses` remains available as a fallback for areas with
  no real building data at all.
- `estimate-addresses` and `real-addresses` now default to the real
  Luanda municipality boundary (`aoi.py::load_luanda_aoi()`, an
  irregular polygon via OSM/Nominatim geocoding) instead of a bbox
  square -- verified against real data at full district scale:
  40,082 real streets, 7,508 real OSM buildings, 7508/7508 addressed
  in 82.2s, and in a real browser (the result now visibly traces
  Luanda's actual coastline, not a rectangle). `--radius-km`/
  `radius_km` still works as an explicit override to a bbox square.
- `run_pipeline()`'s postal-ID sequencing can now be backed by a real,
  persistent database instead of only sequencing in memory (see
  `numbering/sequence.py`'s `DbSequenceProvider` and `db/session.py`) --
  `cli.py` and both server routes use it automatically when the add-on's
  Postgres is reachable, so an existing building's postal ID is never
  reassigned even after new buildings are added in a later run.
- Real OSM buildings are now classified by type (`ingestion/
  osm_buildings.py::classify_building_type`, from OSM's own `building`
  tag) into house/apartment/warehouse/other, and existing OSM
  `addr:street`/`addr:housenumber` tags are captured too (as reference
  fields alongside this project's own computed address, not used to
  generate it). Verified against the full real Luanda AOI: 2436 house,
  313 apartment, 212 warehouse, 4547 other (out of 7508); 2065 already
  carry a real OSM street name. No building in Luanda's OSM data is
  literally tagged "warehouse" -- "industrial" is used as the closest
  real proxy (see `ingestion/osm_buildings.py`'s docstring for the full
  tag mapping). The "Assign addresses (real OSM buildings)" viewer
  layer colour-codes markers by type and shows both addresses in the
  popup; `real-addresses`' CLI output/CSV include the breakdown and new
  columns. This does NOT apply to `estimate-addresses` (its grid-sampled
  points have no OSM tags to classify).

## What is NOT done yet -- do not assume otherwise

- `ingestion/osm_streets.py` and the new `ingestion/osm_buildings.py`
  are wired in (via `estimate-addresses` and `real-addresses`, see
  above) and verified against real Luanda data. `number-district`
  still consumes already-ingested GeoJSON directly, independent of any
  ingestion module.
- `ingestion/open_buildings.py` (Google Open Buildings, merged with
  Microsoft Building Footprints + OSM via VIDA's combined dataset on
  Source Cooperative) is now real and verified (2026-09-22) -- ~861K
  candidate buildings for Luanda vs OSM alone's 7,508. NOT wired into
  `estimate-addresses`/`real-addresses` (the addressing CLI commands
  still use OSM only); currently used as the label source for
  `detect-buildings-ml`'s training data instead -- see discrepancies.md
  "Own neural network for built-up detection" for why OSM's coverage
  turned out too sparse for that use case specifically.
- `enderata detect-buildings-ml` (CLI only, added 2026-09-22) -- LOCAL/
  OPTIONAL real per-building segmentation from a trained U-Net
  (`ml/model.py` + `ml/predict_buildings.py`), best_val_iou=0.6098,
  visually verified to detect individual house rooftops in dense
  blocks (not just large structures -- see discrepancies.md). Needs
  `pip install -r requirements-ml.txt` (torch) and a checkpoint trained
  locally first; both are intentionally absent from `requirements.txt`
  and the add-on's Docker image -- the command lazy-imports torch and
  fails with a clear message if it's missing, so the rest of the CLI
  keeps working without it. NOT wired into the server/viewer, and NOT
  usable for the distributed commercial product: the checkpoint is a
  derivative of Maxar's CC BY-NC 4.0 Open Data Program imagery
  (prototype/local use only until retrained on properly licensed
  imagery).
- **Nationwide (any Angola place, not just Luanda) support, added
  2026-09-22** -- `aoi.py::load_aoi(place_query)` resolves any real
  place via OSM/Nominatim (e.g. `--place "Huambo, Angola"`);
  `load_luanda_aoi()` still works unchanged. New `--place` flag on
  `satellite-builtup`/`estimate-addresses`/`real-addresses` (NOT on
  `detect-buildings-ml` -- that stays Luanda-only, Maxar imagery
  doesn't exist elsewhere). New `--building-source open_buildings` flag
  on `real-addresses` (default stays `osm`): uses
  `ingestion/open_buildings.py`'s Google/Microsoft/OSM combined
  dataset instead of OSM alone -- ~861K candidates for Luanda's AOI vs
  OSM's 7,508, and unlike OSM/Maxar this dataset genuinely covers all
  of Angola. No address/type tags from this source though --
  `building_type` is always `"other"`. Verified for real:
  `satellite-builtup --place "Huambo, Angola"` ran fully end-to-end
  (real Sentinel-2 scene, 15,392 polygons, real Huambo coordinates);
  Open Buildings itself verified nationwide (1,182,378 real buildings
  for Huambo province, queried directly). `real-addresses
  --building-source open_buildings`'s full path (which also needs
  `osm_streets.py`'s Overpass fetch) hit a likely-transient
  connectivity issue during testing in this environment -- not yet
  re-verified live end-to-end, see discrepancies.md § Nationwide
  expansion. `duckdb>=1.0` added to `requirements.txt` (ships in the
  add-on now).
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
- The Luanda district AOI boundary is now real (`aoi.py::load_luanda_aoi()`,
  see above, added 0.1.20) for `estimate-addresses`/`real-addresses`.
  `number-district`/`export-demo` still consume whatever GeoJSON they're
  pointed at directly, independent of the AOI module.
- `pipeline.py` still DEFAULTS to sequencing postal IDs by sorting
  building IDs in memory -- valid only for a fixed, closed input set.
  As of 0.1.20 this is no longer the only option: pass a
  `DbSequenceProvider` (`numbering/sequence.py`) for a real, persistent
  DB-backed sequence instead; `cli.py`/server routes now do this
  automatically via `db/session.py` when the add-on's Postgres is
  reachable, falling back to in-memory (logged) otherwise. The fallback
  and the SQLAlchemy logic are verified (real SQLite, see `tests/
  integration/test_persistent_sequence.py`) -- the actual connection to
  the add-on's bundled Postgres is not yet confirmed on a real HA run.
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
6. (Items 1, 3, 5 above are now done -- see the Resolved table in
   `project_log.md` -- kept here as history, not rewritten.) In
   progress, multi-session: a custom neural network (`enderata/src/
   enderata/ml/`) trained on Sentinel-2 bands + real OSM building
   footprints as labels, to replace the hand-tuned NDBI/NDVI threshold
   rule with a learned one. Scope explicitly limited to a per-pixel
   built-up predictor, not per-building segmentation (no commercially-
   licensed sub-metre imagery exists for Luanda -- see `discrepancies.md`
   § Own neural network for built-up detection for the full scope
   discussion and progress). Not yet integrated into the CLI/viewer.
