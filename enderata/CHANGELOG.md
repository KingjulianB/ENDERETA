# Changelog

## 0.1.19
- New "Assign addresses (real OSM buildings)" button + `enderata
  real-addresses` CLI command. A second, preferred addressing path
  alongside `estimate-addresses`: real OSM-mapped buildings (new
  `ingestion/osm_buildings.py`, via `ox.features_from_bbox(bbox,
  tags={"building": True})`) + real OSM streets -> `run_pipeline()`,
  with no Sentinel-2 fetch at all. Verified against real Luanda data:
  749/749 real OSM-mapped buildings addressed (~1.2s, no satellite
  call needed) and in a real browser (new distinct green layer).
- Investigated wiring in Google Open Buildings first (the originally-
  discussed "real footprints" source): license is genuinely clean
  (CC-BY-4.0/ODbL, confirmed), but its Source Cooperative hosting uses
  a non-standard S3-compatible endpoint that doesn't resolve as
  documented and hit rate-limiting during exploration -- real
  engineering effort for an uncertain payoff. Found real OSM building
  footprints already exist for Luanda instead (same Overpass mechanism
  already used for streets, 749 buildings in the default AOI) and are
  far simpler to use reliably today. Decision (user's explicit choice):
  ship OSM buildings now, keep Google Open Buildings as a planned
  follow-up to fill gaps OSM hasn't mapped -- not a replacement.
- `estimate-addresses` (grid-sampled points, previous feature) remains
  available as a fallback for areas with no real building data at all.
  34/34 tests still passing (no new pure-logic units to test in
  `osm_buildings.py` -- it's a thin osmnx wrapper, same precedent as
  `open_buildings.py` having none).

## 0.1.18
- `numbering/street_assignment.py`'s nearest-street search now uses a
  shapely `STRtree` spatial index (new `StreetIndex`, built once per
  `run_pipeline()` call and reused for every building) instead of a
  linear scan over every street. Verified against a real 20km-radius
  Luanda extract (897 estimated buildings x 268,753 real OSM streets):
  the street-assignment stage dropped from ~675s (measured, the
  previous dominant cost by far) to 1.2s -- the whole
  estimate-addresses run at that radius is now ~61s total, dominated
  by the real Overpass (43.3s) and Sentinel-2 (14.1s) network fetches,
  not computation.
- API change (internal, one real caller): `assign_building_to_street`
  now takes a `StreetIndex` instead of a raw `list[Street]`. Updated
  `pipeline.py` (builds the index once, outside the per-building loop)
  and `tests/unit/test_street_assignment.py` (+1 new test for an empty
  index). 34/34 tests passing.

## 0.1.17
- New "Assign addresses (estimated)" button in the viewer + `enderata
  estimate-addresses` CLI command. Chains three things into the
  existing numbering pipeline: real OpenStreetMap streets (`ingestion/
  osm_streets.py`, rewritten to use `ox.graph_from_bbox` -- the
  previous version used the wrong osmnx API and was never exercised
  against real data), estimated building points grid-sampled inside
  the Sentinel-2 built-up mask (new `satellite/building_estimate.py`,
  capped at 1000 points by default -- `street_assignment.py`'s
  nearest-street search has no spatial index, so an uncapped grid over
  a real city-scale built-up area, ~29km^2 for the current Luanda AOI,
  produced 18000+ points and would have made the button impractically
  slow), and the unchanged `pipeline.py::run_pipeline`.
- **These building locations are ESTIMATES, not real building
  footprints** -- Sentinel-2 is 10m/pixel (see `satellite/built_up.py`'s
  docstring). Output is written to its own `estimated_buildings.geojson`/
  `estimated_streets.geojson` files, rendered as a distinct purple
  layer with an on-screen disclaimer, so it's never confused with the
  synthetic demo fixture or the raw satellite mask layer.
- Verified end-to-end against real Luanda data: 2305 real OSM street
  edges fetched live, 999/999 estimated building points addressed,
  ~20s total (real Sentinel-2 fetch + real Overpass fetch + numbering),
  checked in a real browser (chrome-devtools). Caught and fixed a real
  bug along the way: the server route's JSON response used the key
  `count`, but the viewer's JS read `result.n_addressed` -- showed up
  as a literal "undefined addresses assigned" note on first render.
- 33/33 tests passing (5 new tests for `building_estimate.py`'s point
  sampling/cap/edge-cases, 5 for `osm_streets.py`'s name-cleaning
  fallback logic).

## 0.1.16
- **Pilot district changed from Huambo to Luanda.** Rationale: real,
  open (CC-BY 4.0) high-resolution imagery exists for Luanda via
  OpenAerialMap (a 2017 Maxar mosaic, 0.5m/pixel, confirmed via their
  live API) -- none exists for Huambo at any usable resolution or
  licence (Planet NICFI and OSM-editor imagery layers were both
  checked and ruled out on licensing grounds). Full pivot, not a
  side-by-side option: `LUANDA_CENTRE` replaces `HUAMBO_CENTRE`
  everywhere, `district_code`/`aoi_district` defaults are now
  `LUA`/`luanda`, and `tiles/luanda.mbtiles` (regenerated with
  Planetiler, same process as before, see `tiles/README.md`) replaces
  `tiles/huambo.mbtiles`.
- Verified end to end again after the switch, not assumed to still
  work: real Sentinel-2 fetch over Luanda's actual coordinates (240
  built-up polygons, true-colour/NDBI/NDVI images all render
  correctly), and a real browser check of the new vector tile basemap
  -- which caught a genuine new bug: Luanda's AOI includes a named
  water body (the bay), producing a `water_name` vector layer that
  didn't exist in Huambo's smaller tileset and wasn't in the viewer's
  style list, showing up as an unstyled default blue marker. Fixed by
  adding it to the hidden-layers list.
- 23/23 tests passing (updated `test_tileserver.py` to check the new
  Luanda tile coordinates/bounds instead of Huambo's).

## 0.1.15
- Diagnosing "no map at all" reported on a real HA run: verified the
  committed `tiles/huambo.mbtiles` is byte-identical on GitHub (sha256
  matches local), the Dockerfile's `COPY tiles ./tiles` is present, no
  `.dockerignore` excludes it, and `map.js`'s vector tile layer code is
  unchanged from what was confirmed working in a real browser just
  before the previous push -- could not reproduce the failure locally.
- Hardening while the root cause is confirmed: `/tiles/<z>/<x>/<y>.pbf`
  previously raised an unhandled 500 if the mbtiles file were ever
  missing at runtime, with nothing logged -- a silently blank basemap
  is indistinguishable from a dozen other causes without a log line.
  Now logs clearly at import time ("found ... " or "WARNING: ... does
  not exist") and per failed request, and returns a clean 404 instead
  of crashing.
- Added `.gitattributes` marking `*.mbtiles`/`*.png`/`*.pdf` as binary
  explicitly -- `git check-attr` showed these were previously
  undeclared ("text: unspecified"), protected only by git's heuristic
  auto-detection. No corruption found this time, but this removes the
  risk for good on any future clone/checkout.
- Next: read the add-on's own log (Settings -> Add-ons -> ENDERETA ->
  Log) after updating to this version -- it will now say directly
  whether huambo.mbtiles was found in the container.

## 0.1.14
- Fix: the basemap's building/landcover/landuse/park polygons rendered
  as a solid, over-saturated blob with dark cell-like seams on a real
  HA run (screenshot) instead of the pale, readable style tested here.
  Root cause: those layers used translucent fills (fillOpacity
  0.35-0.5), and OpenMapTiles data for them is made of many small,
  sometimes-overlapping polygons -- semi-transparent overlapping fills
  stack (N overlaps of 0.35 opacity combine toward
  1-(1-0.35)^N, reaching near-opaque within a few overlaps), which is
  exactly what produced the blob. Switched every fill layer to
  fillOpacity: 1 with pre-chosen pale colours instead, which can't
  stack into something darker no matter how much the source geometry
  overlaps. Verified in a real browser across multiple zoom levels
  (zoomed out, default, zoomed in to individual buildings) and with
  demo data loaded on top.

## 0.1.13
- Add a real self-hosted basemap: `enderata/tileserver.py` reads
  vector tile blobs directly out of `tiles/huambo.mbtiles` (generated
  offline with Planetiler -- see `tiles/README.md`), served at
  `GET /tiles/<z>/<x>/<y>.pbf` (TMS->XYZ row conversion verified
  against real data: the independently-computed tile covering Huambo's
  centre matches the stored row exactly). Dockerfile now bundles
  `tiles/` into the image.
- Viewer: added Leaflet.VectorGrid (not a MapLibre migration -- keeps
  every already-tested layer, button and panel unchanged) rendering
  this tileset as the map's base layer -- roads, buildings, water,
  landuse. Fixed a real rendering bug found via an actual browser
  screenshot: OpenMapTiles layers with no explicit style
  (`housenumber`, `poi`, `place`, etc.) fell back to Leaflet's default
  blue marker/path style, showing as stray blue circles/lines; now
  explicitly hidden.
- Verified end to end in a real browser (chrome-devtools, not just
  Python tests): basemap renders correctly, demo data load/clear still
  works on top of it, satellite layer + threshold panel still work
  together with it. 3 new unit tests (tileserver against the real
  committed mbtiles file), 23/23 passing.

## 0.1.12
- Fix: the true-colour/NDBI/NDVI image overlays added in 0.1.9 were
  only visible after manually checking their box in the layer control
  -- off by default, so the panel only ever showed the neutral grey
  background plus the built-up mask, which is exactly what was
  reported ("just the grey and the red"). The real Sentinel-2 photo is
  the whole point of this panel, so it's now shown by default
  (underneath the semi-transparent mask); NDBI/NDVI heatmaps stay
  opt-in via the layer control, to avoid three overlapping heatmaps at
  once.

## 0.1.11
- Fix: "Clear demo data" (and likely other 0.1.10 button changes)
  appeared to do nothing -- almost certainly the same class of issue
  as the earlier OSM-tile fix needing a hard refresh: the browser (via
  HA's ingress iframe) served a cached `map.js` that predated the new
  button's event listener, so the new HTML button existed but had no
  behaviour attached, silently. Root-caused instead of just asking for
  another hard refresh: the server now sends `Cache-Control: no-cache,
  no-store, must-revalidate` on `/`, `/index.html` and `/map.js`, so
  the browser always revalidates instead of serving a stale copy.
  Verified via Flask's test client (200 OK, correct header present).

## 0.1.10
- Fix: loading the satellite layer after loading demo data (or from
  the default view) showed nothing -- `fetchSatellite()` never called
  `map.fitBounds()`, so the map stayed wherever it was (often zoomed
  tight on the tiny demo fixture) instead of jumping to the satellite
  scene's real extent. Now calls `map.fitBounds(imgBounds)` after
  adding the layers.
- Add a "Clear demo data" button -- there was previously no way to
  remove the demo buildings/streets layer from the map once loaded
  (only re-load it). Removes it from the map view only; the underlying
  `buildings.geojson`/`streets.geojson` files are untouched, so
  "Load demo data" still works again afterwards.

## 0.1.9
- Add `enderata/satellite/visualize.py` (Pillow-based, no matplotlib):
  renders the true-colour (percentile-stretched RGB) and NDBI/NDVI
  index images to PNG. `detect_built_up_area(..., image_dir=...)`
  saves them alongside the mask; both the CLI and
  `/api/load-satellite` now do this by default.
- Viewer: the satellite panel now shows a Leaflet layer-control
  letting you toggle the built-up mask, the real true-colour image,
  and the NDBI/NDVI heatmaps independently (georeferenced image
  overlays, positioned from `bounds_wgs84`) -- so you can visually
  compare the mask against the actual processed imagery instead of
  only seeing the final polygons.
- `ndbi_threshold`/`ndvi_threshold` are now adjustable: sliders in the
  panel plus a "Recompute" button call `/api/load-satellite` again
  with the chosen values (also exposed as `--ndbi-threshold`/
  `--ndvi-threshold` on the CLI) -- lets the threshold be tuned by eye
  against the real imagery without needing a code change each time.
- Verified live: recomputing with different thresholds against the
  real Huambo scene changes the polygon count as expected (199 -> 399
  when loosening both thresholds), and all three PNGs render
  correctly.

## 0.1.8
- Wire the Sentinel-2 built-up module into both the CLI and the
  running add-on:
  - `enderata satellite-builtup [--lat --lon --radius-km --out
    --max-cloud-cover]` -- defaults to Huambo's verified centre,
    1.6km radius. Verified live: 199 real polygons from today's
    actual Sentinel-2 scene.
  - `POST /api/load-satellite` on the viewer server -- same pipeline,
    triggered from the web UI (needs outbound internet from the add-on
    host to reach the public AWS STAC catalog). Verified via Flask's
    test client, 200 OK, 199 features written to disk.
  - Viewer: a second toolbar button ("Load satellite layer"), a
    visually distinct orange semi-transparent layer (never styled like
    the numbered buildings/streets so the two can't be confused), and
    an on-screen disclaimer naming the real scene used
    (id/date/cloud-cover) and stating plainly this is a coarse signal,
    not building footprints.

## 0.1.7
- Add `enderata/satellite/` (new, not yet wired into the running
  add-on's CLI/UI): fetches Sentinel-2 bands from the public AWS Earth
  Search STAC catalog (free, no API key, confirmed commercial-use-safe
  under Copernicus' open data policy) and computes a coarse "built-up
  area" mask from NDBI+NDVI. This is the free, legally-clean path for
  a sovereignty-aligned satellite signal while there's no budget for
  the high-res imagery SpaceNet-based building detection would need.
  Verified against a real, current Sentinel-2 scene over Huambo's
  actual (now-confirmed) centre -- caught a tile-boundary bug along
  the way. Explicitly NOT building-footprint detection (10m/pixel);
  documented as a density/extent signal only. 4 new unit tests, 20/20
  passing.
- Fixed Huambo's centre coordinates in the viewer from an unverified
  approximation to a confirmed value (cross-checked against Wikipedia/
  geodatos.net and a real satellite image); the old value was already
  accurate to ~30m, so this changes nothing visible, just removes a
  "not verified" caveat.
- New dependencies: `rasterio`, `pystac-client` (added to
  requirements.txt/pyproject.toml -- increases the Docker image's
  build time/size, not yet exercised in that environment).

## 0.1.6
- Fix: 0.1.5's fixture-in-image fix assumed the user could run
  `docker exec` from HA's "Terminal & SSH" add-on -- that add-on is
  sandboxed with no docker socket access, so `docker` isn't available
  there for most users (real error seen: `docker: command not found`).
  Removed the dependency on shell/docker access entirely: added
  `POST /api/load-demo` to `viz/server.py`, which runs the pipeline
  against the bundled synthetic fixture and writes to `/data/export`
  server-side, plus a "Load demo data" button in the viewer that calls
  it and reloads the map. Verified end to end with Flask's test client
  (5/5 features, correct IDs/addresses) before pushing.
- `loadLayer()` now cache-busts its GeoJSON fetches (`?t=timestamp`) so
  clicking the button shows fresh data immediately instead of a
  browser-cached copy of the previous load.

## 0.1.5
- Fix: viewer confirmed working (no more OSM 403) but showed a blank
  grey map, because nothing ships data into `/data/export` and the
  Docker image never included the synthetic fixture used to verify the
  pipeline. Added `COPY tests/fixtures/synthetic_sample
  ./fixtures/synthetic_sample` to the Dockerfile so
  `enderata number-district` has something to run against via
  `docker exec` without needing real Huambo data yet.

## 0.1.4
- Fix: every basemap tile 403'd with "Access blocked -- App is not
  following the tile usage policy of OpenStreetMap's volunteer-run
  servers" (seen on a real HA run, screenshot). OSM's tile usage policy
  explicitly forbids using tile.openstreetmap.org from a
  packaged/distributed app without prior OSMF approval -- this add-on
  is exactly that case. Removed the raster tile layer rather than swap
  in another third-party host with unverified terms; the viewer now
  renders on a neutral background and auto-fits to whatever GeoJSON
  loads. Choosing a compliant basemap (licensed provider or self-hosted
  tiles) is a deployment-time decision, not fixed here.
- Confirms the full pipeline now renders through HA ingress end to end
  (map loads, addon reachable) -- this add-on has gone from "does not
  build" to "runs and serves a page" across 0.1.1-0.1.4.

## 0.1.3
- Fix: `CREATE EXTENSION postgis` failed with "extension is not
  available" / missing `postgis.control` even though `apt-get install
  postgis` had run. On Debian, the plain `postgis` package is client
  tools/loaders only -- the server-side extension ships in the
  version-specific `postgresql-15-postgis-3` package, now installed
  explicitly alongside it.
- The earlier `pg_ctl` log-permission fix (0.1.1) is confirmed working
  on a real HA run: the server now starts successfully before hitting
  the postgis error above.

## 0.1.2
- Add `icon.png` (128x128) and `logo.png` (256x256): a navy rounded-
  square map-pin mark with a teal centre dot, echoing the business
  plan's navy/teal palette. Generated programmatically (Pillow), not a
  guessed/downloaded asset.

## 0.1.1
- Fix: `pg_ctl` failed with "cannot create /data/postgres.log:
  Permission denied" -- the postgres user only owns `/data/postgres`
  (chowned explicitly), not `/data` itself. Log now goes to
  `${PGDATA}/postgres.log`. Also pre-create and chown
  `/var/run/postgresql` (Debian's compiled-in default unix socket dir),
  since running initdb/pg_ctl by hand skips the Debian package's own
  setup for that directory.
- Fix: `bashio` install step 404'd (`raw.githubusercontent.com/.../bashio/master/install.sh`
  no longer resolves) and was dead code anyway -- nothing called bashio.
  Removed it; `run.sh` now reads add-on options straight from
  `/data/options.json` via `jq` (already installed) instead.
- Fix: HA Supervisor build failed with `apt-get: not found` because
  `build.yaml`'s `python:3.12-slim-bookworm` value didn't match
  Supervisor's expected `namespace/image[:tag]` format, so it silently
  fell back to HA's Alpine base image. Removed `build.yaml` and
  hardcoded `FROM python:3.12-slim-bookworm` in the Dockerfile instead
  (per Supervisor's own "move build parameters into the Dockerfile
  directly" deprecation notice). Found via a real build on the user's
  HA Supervisor.
- Fix: `repository.yaml` / `config.yaml` now point at the real repo
  (`https://github.com/KingjulianB/ENDERETA`) instead of a placeholder.

## 0.1.0
- Initial scaffold: HA add-on packaging (config.yaml, build.yaml,
  Dockerfile, run.sh, ingress-served viewer).
- PostGIS-backed schema (streets, buildings, addresses).
- Permanent postal-ID generation with a MOD 97-10 style check digit
  (unit-tested).
- Street-based house numbering: nearest-street assignment, side
  detection, odd/even ordering (unit-tested).
- `pipeline.py` orchestration (street assignment -> numbering ->
  postal ID -> address) plus `enderata number-district` CLI command.
  Verified end to end against a 5-building synthetic fixture, including
  an automated permanence regression test (identical postal IDs across
  reruns) and an ID/address-separation test. 16/16 tests passing.
- Static Leaflet demo viewer.
- Ingestion modules (Open Buildings, OSM) are structurally complete but
  NOT exercised against real data/network in this session, and not yet
  wired into the CLI.
- Docker/Postgres startup path NOT build/run-tested -- no Docker
  runtime available in this development environment.
