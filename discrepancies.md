# ENDERETA — Open Discrepancies & Topics Needing Human Analysis

**Started:** 2026-09-20. Append-only-ish log: add new findings under `##
Open`, grouped by topic. Once resolved, move the entry to `## Resolved`
with the answer documented — don't delete it.

Purpose: this file holds genuine technical mismatches and open
questions — not a general to-do list. Unfinished-but-unblocked work
belongs in the current `dayX_objectives.md` instead.

---

## Open

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
- **Status:** SpaceNet path was blocked on imagery budget/licensing for
  Huambo (checked and ruled out: NICFI, OSM editor imagery layers) —
  the Luanda switch may change this, untested. Sentinel-2 NDBI/NDVI
  path built, tested (4 new unit tests, 23/23 total passing), verified
  against real Luanda data — usable today as a free, legally-clean,
  coarse sovereignty-aligned signal, with its precision limits
  documented rather than overstated.

### Real Luanda AOI boundary (renamed from "Real Huambo AOI boundary",
### pilot district changed 2026-09-22)

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
- **Status:** not provided. Nothing in this project has touched real
  Luanda geodata yet (beyond the Sentinel-2/vector-tile verification
  already done) — every numbering-pipeline "it works" claim so far is
  scoped to the synthetic fixture only.

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
