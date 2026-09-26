# Changelog

## 0.1.25
- **Nationwide basemap**: self-hosted vector tiles (`tiles/`) switched
  from a Luanda-only clip (`luanda.mbtiles`, 696KB) to the whole
  country (`angola.mbtiles`, 154MB, 298,207 tiles, same Planetiler
  build, no `--bounds` clip this time). `tileserver.py`/`server.py`
  updated; old file removed.
- **Nationwide place selection added to the viewer** (previously
  CLI-only via `--place`) -- a new "Place" panel (place name, district
  code, building-source dropdown) lets `/api/load-satellite`,
  `/api/estimate-addresses` and `/api/real-addresses` run against any
  real Angolan place, not just Luanda. Empty place still defaults to
  Luanda (no behaviour change for existing use). Verified for real
  against Huambo through the live HTTP API.
- Satellite imagery stays fetched live per place rather than
  pre-rendered nationwide (decision made explicitly with the user,
  given a full-country raster mosaic would need gigabytes of
  pre-processed tiles) -- see discrepancies.md.

## 0.1.24
- **Fixed: built-up mask was classifying open water as built-up/
  habitable** (user: "j'ai vue que le masque confond la mer comme une
  zone habitable"). Sampled real pixels over Luanda's real coastline:
  the old NDBI+NDVI mask flagged 73% of clearly-water pixels as
  built-up -- a real coastal lagoon hit the classic published NDBI/
  water confusion, and very dark near-sensor-noise-floor deep-ocean
  pixels made every ratio-based index numerically unstable.
- Fixed in `satellite/built_up.py`: new `compute_mndwi()` (Green vs
  SWIR -- the standard remote-sensing fix for NDBI's own water
  confusion, since NDBI itself is SWIR-based) plus a minimum-
  brightness gate (sum of all four bands) that excludes near-zero-
  reflectance pixels outright, since no index threshold is numerically
  trustworthy there regardless. `mndwi.png` now also saved alongside
  `ndbi.png`/`ndvi.png` for visual inspection.
- Verified twice on real data (the diagnostic pass, then again on a
  fresh production CLI run): water pixels wrongly flagged as built-up
  dropped from 58,572 to 2,276 (96% reduction), with real urban pixels
  comfortably clear of the new brightness floor (no measurable loss of
  real coverage). 80/80 tests pass (4 new).

## 0.1.23
- **Nationwide (any Angola place, not just Luanda) support** (user:
  "okay je veux le faire sur toute l'Angola"). `aoi.py::load_aoi()`
  resolves any real place via OSM/Nominatim; new `--place` flag on
  `satellite-builtup`/`estimate-addresses`/`real-addresses`.
- **Open Buildings as a real addressing source**: new `--building-source
  open_buildings` flag on `real-addresses` (default stays `osm`) uses
  the Google/Microsoft/OSM combined dataset (`ingestion/open_buildings.py`)
  instead of OSM alone -- ~861K candidates for Luanda's AOI vs OSM's
  7,508, and covers the whole country (unlike OSM or the Maxar-based
  ML model, which stays Luanda-only). No address/type tags from this
  source: `building_type` is always `"other"`.
- `duckdb>=1.0` added to `requirements.txt` -- the first dependency
  this feature needed that actually ships in the add-on's Docker image
  (Open Buildings has a clean CC-BY-4.0/ODbL license, unlike the
  Maxar-derived ML model, and duckdb is a small compiled wheel, unlike
  torch).
- Verified for real: `satellite-builtup --place "Huambo, Angola"` ran
  fully end-to-end (real Sentinel-2 scene, 15,392 polygons, real Huambo
  coordinates); Open Buildings itself verified nationwide (1,182,378
  real buildings for Huambo province). `real-addresses
  --building-source open_buildings`'s full path (also needs OSM
  streets) hit a likely-transient Overpass connectivity issue during
  testing -- not yet re-verified live end-to-end, see discrepancies.md.
  77/77 tests pass.

## 0.1.22
- **Built-up mask now covers all of Luanda** (user request: "je veux
  que le buld up mask soit sur tout luanda"). "Load satellite layer"
  (viewer button, `POST /api/load-satellite`) and `satellite-builtup`
  (CLI) now default to the real Luanda AOI polygon (same `aoi.py` used
  by `estimate-addresses`/`real-addresses`) instead of a fixed 1.6km
  radius; `radius_km` stays available as an explicit bbox-square
  override.
- Fixing the scope required fixing a real bug first: `read_bands`
  (`satellite/sentinel2.py`) forced every bbox into a SQUARE raster
  (`out_shape=(out_size, out_size)`, previously fixed at 600x600) --
  harmless for the old near-square 1.6km test AOI, but the real Luanda
  municipality is ~15km x 18km, so a forced square would have badly
  distorted the mask's aspect ratio. Also found and fixed the root
  cause of an earlier-documented oddity (returned `bounds_wgs84` being
  roughly double the requested bbox, noted but not explained in an
  earlier session): the bounds were computed from a NATIVE-resolution
  transform combined with the RESAMPLED array's pixel count -- an
  internally inconsistent pairing. New `_compute_out_shape` sizes the
  output to the bbox's real aspect ratio at ~10m/pixel (Sentinel-2's
  native resolution), capped at `max_dimension` (default 2000px on the
  longer side, both sides scaled together so aspect ratio is
  preserved); bounds are now computed directly from the read window's
  real geographic extent, independent of how it's resampled.
- Verified for real: requested vs. returned bbox now match to ~0.001°
  (was ~2x off before), full-Luanda run completes in 17.8s and returns
  24,435 built-up polygons (vs. a few hundred at the old 1.6km-radius
  scope) -- checked in a real browser (the true-colour/mask overlay now
  visibly traces the real coastline/bay, not a stretched square). 4 new
  unit tests for `_compute_out_shape`'s aspect-ratio/cap/edge-case
  behaviour. 55/55 tests passing.

## 0.1.21
- **Building-type classification** (user request: "je ne detecte pas
  les maison sur mon algo... je veux detecte maisons immeuble et
  entrepot"): before changing anything, checked the real OSM data --
  no bug found, houses/apartments were already being fetched (OSM's
  `building` tag was just never surfaced or shown differently in the
  output/viewer). New `ingestion/osm_buildings.py::classify_building_type`
  maps OSM's `building` tag to house/apartment/warehouse/other,
  verified against the full real Luanda AOI (7508 buildings: 2436
  house, 313 apartment, 212 warehouse, 4547 other). No building in
  Luanda's real OSM data is literally tagged "warehouse" -- "industrial"
  is used as the closest real proxy, documented as a judgment call, not
  a guess about data that doesn't exist.
- **Existing OSM street names/addresses captured too** (user request:
  "prend aussi les noms des rue existante"): `osm_street_name`/
  `osm_housenumber` (from OSM's own `addr:street`/`addr:housenumber`
  tags) are now captured and carried through as reference fields
  alongside this project's own computed address -- 2065/7508 real
  buildings in the full Luanda AOI already carry a real `addr:street`
  tag.
- `pipeline.py::AddressedBuilding`/`run_pipeline`/`to_feature_collection`
  extended with optional `building_type`/`osm_street_name`/
  `osm_housenumber` fields (default None, so the synthetic fixture and
  `estimate-addresses`' grid-sampled points -- neither has OSM tags --
  are unaffected). Viewer's "Assign addresses (real OSM buildings)"
  layer now colour-codes markers by type (teal=house, orange=apartment,
  brown=warehouse, green=other) and shows both addresses in the popup;
  `real-addresses`' CLI output/CSV include a type breakdown and the two
  new columns.
- Caught and fixed a real bug while building this: geopandas silently
  turned a Python `None` into a float `NaN` when a GeoDataFrame column
  was built from a plain list mixing `None` and strings (`osm_buildings.py`'s
  output) -- `run_pipeline()` now normalizes NaN to None itself rather
  than trusting the input, with a regression test reproducing the exact
  bug. Verified end-to-end against real Luanda data (color-coded
  markers, enriched popups) in a real browser.
- 51/51 tests passing (13 new: classification + NaN/None regression).

## 0.1.20
- **Real Luanda AOI boundary** (new `aoi.py`): `estimate-addresses` and
  `real-addresses` (CLI + viewer buttons) now default to the real
  Luanda municipality boundary polygon (`ox.geocode_to_gdf`, verified
  as "Luanda, Municipality of Luanda, Luanda Province, Angola" -- an
  irregular ~15km x 18km shape, not the previous `bbox_from_center`
  square). `osm_streets.py`/`osm_buildings.py` switched to
  `ox.graph_from_polygon`/`ox.features_from_polygon` so results are
  clipped to the real boundary; the Sentinel-2 built-up mask (still
  bbox-based -- rasterio needs a rectangular window) is clipped to the
  real AOI afterward before sampling. `--radius-km`/`radius_km`
  remains as an explicit override to a bbox square (used for the
  large-radius stress tests). Verified end-to-end against the real,
  full Luanda AOI: 40,082 real streets, 7,508 real OSM buildings,
  7508/7508 addressed, 82.2s -- and in a real browser (the addressed
  layer now visibly traces the city's actual irregular coastline
  shape, not a square).
- **Persistent postal-ID sequencing** (new `numbering/sequence.py`,
  `db/session.py`, `PostalSequence` table in `db/models.py`):
  `run_pipeline()` takes an optional `sequence_provider`; the previous
  in-memory sorted-building-id behaviour (documented limitation --
  reassigns existing IDs when a new building_id sorts earlier) stays
  the default when no DB is available. `DbSequenceProvider`, backed by
  the `postal_sequences` table, gives each building_id a number once
  and never reassigns it, even across separate runs on a growing
  dataset. Wired into `cli.py` (`number-district`, `estimate-addresses`,
  `real-addresses`) and both server routes via `db/session.py`'s
  `open_sequence_provider`, which connects to the add-on's real
  Postgres (`config.py`'s `DATABASE_URL`) and falls back to in-memory
  sequencing (logged, not a crash) if it's unreachable.
- Verified for real: the actual bug (in-memory provider reassigning
  IDs when a building sorts earlier) reproduced in a new test; the fix
  verified against a real on-disk SQLite database across separate
  sessions (no PostGIS-specific column is involved in this table, so
  SQLite works for testing even though Postgres is the production
  target) -- 4 new integration tests, 38/38 total passing. The
  Postgres connection path itself (`db/session.py`) is exercised
  end-to-end against a real SQLite URL override (success path) and the
  real "no DB reachable" fallback (this dev environment has no
  Postgres) -- but not yet checked against the add-on's actual bundled
  Postgres on a real HA run.

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
