# ENDERETA — Open Discrepancies & Topics Needing Human Analysis

**Started:** 2026-09-20. Append-only-ish log: add new findings under `##
Open`, grouped by topic. Once resolved, move the entry to `## Resolved`
with the answer documented — don't delete it.

Purpose: this file holds genuine technical mismatches and open
questions — not a general to-do list. Unfinished-but-unblocked work
belongs in the current `dayX_objectives.md` instead.

---

## Open

### Own neural network for built-up detection — IN PROGRESS, multi-session

- **Context:** user asked to build ENDERETA's own neural network
  ("creant notre propre reseau de neurone pour tout ca"), reopening the
  "Sovereign building/road detection model" question below with a
  from-scratch-training approach instead of a pretrained model.
- **Scope, confirmed with the user before writing code:** a per-pixel
  "does a real building footprint overlap this cell" predictor trained
  on Sentinel-2 bands, learning a replacement for the hand-tuned
  NDBI/NDVI threshold rule -- NOT per-building instance segmentation
  (SpaceNet-style outlines). At Sentinel-2's 10m/pixel resolution a
  typical building is smaller than one pixel, so individual footprint
  segmentation isn't achievable regardless of model quality; this was
  explained to the user before they confirmed the scope.
- **Imagery source, re-litigated and corrected:** first checked whether
  the 0.5m Maxar mosaic (thought to be CC-BY 4.0, see the correction
  note in the Huambo-to-Luanda pivot entry below) could be used for
  real per-building segmentation instead -- re-verifying its license
  against the raw OpenAerialMap API JSON found it's actually CC-BY-NC
  4.0 (non-commercial), confirmed against Maxar's own Open Data Program
  docs (the whole program is NC-only bar a narrow OSM-specific
  exception). Searched OpenAerialMap broadly around Luanda for any
  other coverage -- found none. No paid alternative pursued (Planet,
  Maxar direct, Airbus Pleiades all mentioned as options, budget not
  confirmed available). User's explicit choice: proceed on Sentinel-2
  despite its resolution ceiling rather than pursue paid imagery.
- **Progress so far (2026-09-22):**
  1. Local GPU (NVIDIA RTX A1000, 6GB) was present but PyTorch was
     installed CPU-only (`torch 2.14.0+cpu`) -- reinstalled the matching
     CUDA 13.2 build (`torch 2.14.0+cu132`), verified with a real matrix
     multiplication on the device, not just `cuda.is_available()`.
  2. New `ingestion/osm_buildings.py::load_osm_building_footprints` --
     keeps real polygon/point geometry (the existing `load_osm_buildings`
     collapses to a centroid, wrong for rasterizing labels).
  3. New `ml/dataset.py`: `rasterize_building_mask` (real OSM footprints
     -> binary label raster, Point geometries buffered since they have
     zero area) + `build_training_dataset` (real Sentinel-2 fetch + real
     OSM footprints, same pixel grid) + save/load (`.npz` + `.json`
     sidecar). Verified against the full real Luanda AOI: 1799x1514px,
     35,277 positive label pixels (1.3% -- consistent with OSM's sparse
     volunteer coverage), 16.1s. Round-tripped through save/load.
     Visually sanity-checked: the label mask overlaid on the true-colour
     image tracks real urban texture (Ilha do Cabo peninsula, downtown
     core), not randomly scattered -- screenshot reviewed, not just
     numbers trusted.
  5 new unit tests for `rasterize_building_mask`'s pure logic (no
     network). 60/60 tests passing.
- **Not done yet:** model architecture (small U-Net, 5 input channels),
  patch/tile extraction with a spatial train/val split, training loop,
  evaluation against the NDBI/NDVI baseline (must show a real
  improvement before replacing anything), integration (CLI/route/
  viewer). User has explicitly accepted this spans multiple sessions.

### Sovereign building/road detection model — CLOSED for now, NDBI/NDVI is the answer

- **2026-09-22, final decision after trying to act on the Luanda
  imagery opening:** attempted to actually use SpaceNet 6 (the model
  path decided 2026-09-20, below) against Luanda's real OpenAerialMap
  imagery. Found a hard technical blocker verified directly in the
  winning solution's own README: *"input to all of my segmentation
  networks is SAR image with 4 channels"* — SpaceNet 6 was trained on
  Capella SAR + Maxar optical fusion (Rotterdam), and its models take
  SAR as input, not plain RGB. Not fixable by more effort; the wrong
  model family for optical-only imagery. Also surfaced a broader
  licensing concern common to the whole SpaceNet family: the training
  dataset is CC BY-SA 4.0, and a credible source states trained model
  weights are treated as a derivative carrying the ShareAlike
  obligation, independent of the training/inference code's own
  (Apache 2.0) license. Searched for a non-SpaceNet alternative
  (optical, building-specific, clearly licensed, well-documented) --
  none exists: Microsoft/Google publish only their output data (ODbL),
  never model weights; Hugging Face's building-segmentation models are
  small, undocumented individual projects with unclear training-data
  provenance (arguably a worse, just less visible, licensing risk than
  SpaceNet); Prithvi (NASA/IBM, genuinely open, well-documented) is a
  general Earth-observation foundation model, not building-specific,
  and runs at Sentinel/Landsat resolution (10-30m) -- would need a full
  fine-tune with labelled data to be useful here, which is the same
  training-data problem this whole detour was trying to avoid.
- **Decision:** stop pursuing a pretrained building-detection model.
  The Sentinel-2 NDBI/NDVI built-up signal (free, legally clean,
  already built and shipping in the add-on) is the sovereignty-aligned
  answer for now. Revisit if/when a clearly-licensed, building-specific
  optical model becomes available, or budget opens up real high-res
  licensed imagery.
- **2026-09-22, real building footprints found via two different
  routes -- one shipped, one deferred:** asked "what can we add", user
  picked pursuing real building footprints. Investigated Google Open
  Buildings (the AI-detected dataset already scoped above, not a new
  model): its data license is genuinely clean (CC-BY-4.0 or ODbL,
  user's choice) and its coverage (58M km^2 across Africa/S.Asia/SE
  Asia/Latin America, generated by Google's own model) would be far
  more exhaustive than OSM's volunteer mapping. But its current
  distribution (Source Cooperative, `data.source.coop/cholmes/google-
  open-buildings/`) uses a non-standard S3-compatible bucket
  (`s3://us-west-2.opendata.source.coop/google-research-open-
  buildings/`) that doesn't resolve as a normal AWS S3 endpoint (DNS
  lookup for a literal `us-west-2.opendata.source.coop` host fails;
  DuckDB's httpfs S3 client also failed against it with a TLS/routing
  error) and the plain HTTPS mirror at `data.source.coop` started
  returning empty responses (rate-limiting, most likely Cloudflare)
  after several probe requests during exploration. Solvable in
  principle (the correct access pattern is documented in a linked
  DuckDB/GeoParquet tutorial gist, just not yet reverse-engineered
  against the *current* hosting layout) but real, non-trivial
  engineering effort for a dataset whose main advantage over OSM is
  completeness, not something blocking today's work.
- **What shipped instead:** real OSM-mapped building footprints
  (`ingestion/osm_buildings.py`, `ox.features_from_bbox(bbox,
  tags={"building": True})` -- same Overpass mechanism already used
  and verified for streets). 749 real buildings confirmed in the
  default 1.6km-radius Luanda AOI, with real `addr:*`/`name` tags on
  many of them (not used -- this project assigns its own addresses).
  Wired into a new "Assign addresses (real OSM buildings)" button/CLI
  command/route (`real_addresses.py`), verified end-to-end and in a
  real browser -- see `project_log.md` Resolved #16.
- **Status:** OSM buildings are real but volunteer-mapped, so coverage
  is genuinely incomplete (this is NOT the same limitation as NDBI/NDVI
  estimation -- every OSM building returned is a real, individually
  mapped structure, there just aren't buildings returned for areas
  nobody has mapped yet). Google Open Buildings remains a planned
  follow-up specifically to fill those gaps with AI-detected coverage,
  not a replacement for the OSM path. `estimate-addresses` (grid-
  sampled points) stays available as a fallback where neither real
  source has data.

### Sovereign building/road detection model — history (closed above)

- **Context:** to reduce dependency on Google Open Buildings (data-
  sovereignty argument central to the business plan's government
  pitch), the user chose to build an independent building/road
  detection capability starting from an existing pretrained model
  rather than training from scratch (2026-09-20).
- **What I found:** SpaceNet 6's winning building-detection models are
  released under **Apache 2.0** (permissive, commercial use OK),
  weights on a public S3 bucket
  (`s3://spacenet-dataset/spacenet-model-weights/spacenet-6/`) — a
  real, checkable option, not a guess. Road extraction has an
  equivalent standard approach (U-Net/D-LinkNet style, trained on
  DeepGlobe) but individual GitHub implementations' licenses still need
  per-repo verification before use. Microsoft's own global building
  footprints are open-DATA (ODbL) but NOT open-model — even large
  players keep trained weights closed while opening outputs, which
  validates starting from a genuinely open-licensed model (SpaceNet)
  rather than trying to extract weights from a closed one.
- **What's still needed:** SpaceNet's models were trained on ~30-50cm/
  pixel commercial imagery — that gap is NOT closed (see below), so the
  SpaceNet building-footprint model itself is still not usable on
  Huambo. Real high-res imagery (paid) or a genuinely free, adequately-
  licensed source remains an open, likely-later item once budget
  exists.
- **2026-09-21, zero-budget path taken instead:** user confirmed no
  imagery budget for now. Checked Planet NICFI's actual license text
  (not just its resolution) — **it's non-commercial-only with a
  share-alike derivative clause**, incompatible with ENDERETA's
  commercial/government-contract model, so it's excluded on legal
  grounds, not just resolution. Sentinel-2 (Copernicus) confirmed free
  for any use including commercial (ESA open data policy).
  Implemented and verified end-to-end against a REAL current scene:
  `enderata/src/enderata/satellite/sentinel2.py` (fetches red/nir/
  swir16 bands via the public AWS Earth Search STAC catalog, no API
  key) + `built_up.py` (NDBI+NDVI built-up mask, vectorized to
  GeoJSON). Caught and fixed a real bug along the way: the
  previously-unverified Huambo coordinate was ~30m off (negligible)
  but sat right on a Sentinel-2 tile boundary, so an unverified nearby
  tile initially returned a half-empty image; the correct tile
  (33LWF) was found by checking actual tile bounds. Visual sanity
  check (mask overlaid on true-colour imagery) confirmed the built-up
  mask tracks Huambo's real street grid and excludes its parks/rivers
  — but is over-inclusive at the city edges (bare/cleared ground reads
  as "built-up", a known NDBI limitation, not fixed here). This is a
  coarse density/extent signal, not a building-footprint replacement —
  documented plainly in the module docstrings.
- **2026-09-22, checked OSM editor imagery layers (Bing/Esri/Maxar via
  the user's OSM account) as another candidate:** ruled out, same
  family of problem as NICFI but stricter. Bing's grant to OSM is
  explicitly "non-commercial online editor application" use only;
  Esri's is "trace features and validate edits" only; Maxar's was
  "only to trace, and validate edits that must be contributed back to
  OSM" (and Maxar revoked this access in July 2023 anyway). None
  permit bulk download or reuse outside the OSM editor -- an OSM
  account does not unlock anything usable here.
- **2026-09-22, pilot district changed from Huambo to Luanda** (see
  `project_log.md` Resolved #10 and below) **potentially reopens this
  path:** OpenAerialMap's real, verified CC-BY 4.0 Luanda coverage (a
  2017 Maxar mosaic) is 0.5m/pixel — right at the edge of what
  SpaceNet's models were trained on (~30-50cm). Not yet tried: fetching
  that mosaic and actually running SpaceNet inference against it. Real
  chance this unblocks proper building-footprint detection where
  Huambo never could — worth a follow-up session, not done here.
  **CORRECTION, same day, later session:** this "CC-BY 4.0" reading was
  wrong. Re-checked against OpenAerialMap's raw API JSON (not a summary)
  while scoping the "own neural network" work below: the API's
  top-level `meta.license` field does say "CC-BY 4.0" (the platform's
  generic default), but this specific image's own `properties.license`
  field — the one that actually governs the asset — says **"CC BY-NC
  4.0"**. Confirmed against Maxar's own Open Data Program documentation:
  the whole program is systematically CC-BY-NC-4.0, with a narrow
  exception letting OpenStreetMap itself (not third parties) use it
  commercially. So this imagery was never usable for ENDERETA's
  commercial/government product — ruled out on the same grounds as
  NICFI, just discovered five months later than it should have been.
  A full re-search for any other sub-metre, genuinely commercial-safe,
  free imagery source for Luanda found none (see the "own neural
  network" section below).
- **Status:** SpaceNet path was blocked on imagery budget/licensing for
  Huambo (checked and ruled out: NICFI, OSM editor imagery layers) —
  the Luanda switch may change this, untested. Sentinel-2 NDBI/NDVI
  path built, tested (4 new unit tests, 23/23 total passing), verified
  against real Luanda data — usable today as a free, legally-clean,
  coarse sovereignty-aligned signal, with its precision limits
  documented rather than overstated.

---

## Resolved

*(see `project_log.md`'s "Resolved" table for the full list of fixed
build/runtime issues — build.yaml/base image, bashio, pg_ctl
permissions, missing postgis package, OSM tile 403s, the accidental
screenshot commit. Those were concrete build/runtime errors with a
single correct fix, not open questions needing a human judgment call,
so they're tracked there rather than duplicated here.)*

### Real Luanda AOI boundary (renamed from "Real Huambo AOI boundary",
### pilot district changed 2026-09-22) — RESOLVED 2026-09-22

- **What I tried:** built and verified the entire numbering pipeline
  (street assignment → house numbering → postal ID → address
  formatting → CLI → viewer) against a hand-made 5-point/2-line
  synthetic fixture (`enderata/tests/fixtures/synthetic_sample/`),
  explicitly labeled as fake data and not moved when the pilot switched
  to Luanda (see the fixture's own README).
- **What's needed:** the actual Luanda district polygon (as a GeoJSON
  boundary) that defines the POC's area of interest, so
  `ingestion/open_buildings.py` and `ingestion/osm_streets.py` have
  something real to clip against.
- **2026-09-22, partial progress:** `ingestion/osm_streets.py` rewritten
  and verified against real Luanda streets (2305 edges via osmnx/
  Overpass), and a new "estimate addresses" feature
  (`estimate_addresses.py`) runs the full pipeline against real streets
  + building points grid-sampled inside the Sentinel-2 built-up mask —
  see `project_log.md` Resolved #14. Still didn't close this item: no
  real AOI boundary polygon yet, no real building footprints.
- **2026-09-22, further progress:** `ingestion/osm_buildings.py` + a new
  "Assign addresses (real OSM buildings)" path (`real_addresses.py`)
  added REAL building footprints where OSM has mapped them (749
  verified). Narrowed the gap but still didn't close this item: the AOI
  was still just a bbox, not a real district polygon.
- **2026-09-22, resolution:** new `aoi.py::load_luanda_aoi()`, via
  `ox.geocode_to_gdf("Luanda, Angola")` (same OSM/Nominatim ecosystem
  already used for streets/buildings) — returns a real, single,
  irregular Polygon: "Luanda, Municipality of Luanda, Luanda Province,
  Angola", bounds (13.1732, -8.9208) to (13.3109, -8.7592), ~15km x
  18km, verified NOT a square. `osm_streets.py`/`osm_buildings.py`
  switched from `graph_from_bbox`/`features_from_bbox` to
  `graph_from_polygon`/`features_from_polygon` so results are clipped
  to the real boundary; the Sentinel-2 mask (still bbox-based, rasterio
  needs a rectangular window) is clipped to the real polygon afterward,
  before sampling. `estimate-addresses`/`real-addresses` (CLI + viewer
  buttons) now default to this real AOI; `--radius-km`/`radius_km`
  stays available as an explicit bbox-square override (used for the
  earlier large-radius stress tests). Verified end-to-end at full
  district scale (40,082 real streets, 7,508 real OSM buildings,
  7508/7508 addressed, 82.2s) and in a real browser — the addressed
  layer visibly traces Luanda's actual irregular coastline, not a
  rectangle.
- **Status:** RESOLVED for the two real-data addressing paths
  (`estimate-addresses`, `real-addresses`). `number-district`/
  `export-demo` still take whatever GeoJSON they're pointed at
  directly, unaffected either way. OSM building coverage inside the
  real AOI is still incomplete (see the Sovereign building/road
  detection model section) — that's a separate, still-open limitation,
  not this one.

### Persistent postal-ID sequencing — RESOLVED 2026-09-22

- **What I tried:** `pipeline.py` currently assigns each building's
  postal-ID sequence number by sorting `building_id` in memory and
  numbering in that order. This is deterministic and passes the
  permanence regression test (`tests/integration/test_pipeline_permanence.py`)
  — but only because the test input never changes between runs.
- **What's needed:** a judgment call on the real mechanism before
  ingestion is wired to a growing dataset: a Postgres sequence keyed by
  `building_id` (so a newly discovered building gets the next unused
  number and nothing already issued ever shifts), versus some other
  scheme. This is a design decision, not something to infer from the
  code.
- **2026-09-22, resolution:** new `numbering/sequence.py`
  (`SequenceProvider` protocol; `InMemorySequenceProvider` = today's
  behaviour, unchanged default; `DbSequenceProvider` = a real
  persistent counter, get-or-assign against a `postal_sequences` table
  keyed by building_id, unique per (country_code, district_code)).
  `pipeline.py::run_pipeline` takes an optional `sequence_provider`.
  New `db/session.py::open_sequence_provider` connects to the add-on's
  real Postgres (`config.py`'s `DATABASE_URL`) and creates the table if
  missing; on any failure it logs a warning and returns `(None, None)`
  so callers fall back to the in-memory default instead of crashing.
  Wired into `cli.py` (`number-district`, `estimate-addresses`,
  `real-addresses`) and both server routes.
- **Verification:** the actual bug (in-memory provider reassigning an
  existing ID when a new building_id sorts earlier) was reproduced in a
  new test first, then the fix verified against a real on-disk SQLite
  database across two separate sessions/runs (no PostGIS-specific
  column is involved in `postal_sequences`, so SQLite works for testing
  even though Postgres is the production target) — 4 new integration
  tests, `tests/integration/test_persistent_sequence.py`.
  `open_sequence_provider`'s success path was also verified end-to-end
  against a real SQLite `DATABASE_URL` override, and its fallback path
  against the real "no DB reachable" case (this dev environment has no
  Postgres).
- **Status:** RESOLVED as a design + implementation, with a
  known-and-logged fallback when no DB is reachable. NOT yet confirmed
  against the add-on's actual bundled Postgres on a real HA Supervisor
  run — `run.sh` already starts Postgres before the server/CLI in that
  environment, so it should just work, but that specific path is
  unverified until checked there directly.
