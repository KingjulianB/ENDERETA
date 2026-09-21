# ENDERETA — Open Discrepancies & Topics Needing Human Analysis

**Started:** 2026-09-20. Append-only-ish log: add new findings under `##
Open`, grouped by topic. Once resolved, move the entry to `## Resolved`
with the answer documented — don't delete it.

Purpose: this file holds genuine technical mismatches and open
questions — not a general to-do list. Unfinished-but-unblocked work
belongs in the current `dayX_objectives.md` instead.

---

## Open

### Compliant basemap for the viewer

- **What I tried:** the standard Leaflet default, `tile.openstreetmap.org`.
  Every tile came back `403 Access blocked` (confirmed via a real
  screenshot from the running add-on): OSM's tile usage policy
  (osm.wiki/Blocked) explicitly requires prior OSMF sysadmin approval
  for any distributed/packaged application — a Home Assistant add-on
  other people can install is exactly that case, so this isn't a
  transient error, it's policy-as-designed.
- **What's needed:** a decision on how to get a real basemap without
  repeating the mistake of guessing a third-party host's current terms:
  - Self-host vector or raster tiles (most compliant long-term, more
    setup work).
  - A licensed provider with an API key you hold (MapTiler, Stadia
    Maps, etc. — needs an account/key, a recurring cost at scale).
  - Keep no basemap for now (current state) and only add one once a
    provider decision is made deliberately, not improvised again.
- **Status:** currently no basemap. `viewer/map.js` renders GeoJSON
  layers on a plain background (`#eef3f5`) and auto-fits the map to
  whatever loads.

### Sovereign building/road detection model — imagery gap (blocks implementation)

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
- **Status:** SpaceNet path still blocked on imagery budget/licensing.
  Sentinel-2 NDBI/NDVI path built, tested (4 new unit tests, 20/20
  total passing), and verified against real data — usable today as a
  free, legally-clean, coarse sovereignty-aligned signal, with its
  precision limits documented rather than overstated.

### Real Huambo AOI boundary

- **What I tried:** built and verified the entire numbering pipeline
  (street assignment → house numbering → postal ID → address
  formatting → CLI → viewer) against a hand-made 5-point/2-line
  synthetic fixture (`enderata/tests/fixtures/synthetic_sample/`),
  explicitly labeled as fake data.
- **What's needed:** the actual Huambo district polygon (as a GeoJSON
  boundary) that defines the POC's area of interest, so
  `ingestion/open_buildings.py` and `ingestion/osm_streets.py` have
  something real to clip against.
- **Status:** not provided. Nothing in this project has touched real
  Huambo geodata yet — every "it works" claim so far is scoped to the
  synthetic fixture only.

### Persistent postal-ID sequencing

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
- **Status:** documented as a known limitation in `pipeline.py`'s
  module docstring; not blocking the current fixture-scale work, but
  blocking before any real/growing dataset is numbered for real.

---

## Resolved

*(see `project_log.md`'s "Resolved" table for the full list of fixed
build/runtime issues — build.yaml/base image, bashio, pg_ctl
permissions, missing postgis package, OSM tile 403s, the accidental
screenshot commit. Those were concrete build/runtime errors with a
single correct fix, not open questions needing a human judgment call,
so they're tracked there rather than duplicated here.)*
