# ENDERETA — Open Discrepancies & Topics Needing Human Analysis

**Started:** 2026-09-20. Append-only-ish log: add new findings under `##
Open`, grouped by topic. Once resolved, move the entry to `## Resolved`
with the answer documented — don't delete it.

Purpose: this file holds genuine technical mismatches and open
questions — not a general to-do list. Unfinished-but-unblocked work
belongs in the current `dayX_objectives.md` instead.

---

## Open

### Built-up mask confused open water with built-up area — RESOLVED 2026-09-22

- **User: "j'ai vue que le masque confond la mer comme une zone
  habitable."** Verified against a real Sentinel-2 scene over Luanda's
  real coastal AOI, sampling actual pixels (not guessing): the old
  NDBI+NDVI mask flagged ~73% of clearly-water pixels (58,572 of
  80,558 very-low-NIR pixels) as `built_up`. Two distinct real causes:
  1. A real, visible coastal lagoon (moderate reflectance) hit the
     classic published NDBI/water confusion: ndbi=0.114 (>0),
     ndvi=-0.040 (<0.3) -- both pass the old thresholds.
  2. Very dark, near-sensor-noise-floor pixels (deep ocean, e.g.
     red=1 green=1 nir=25 swir=124) made EVERY ratio-based index
     numerically unstable -- one such pixel scored ndvi=0.923, high
     enough to dodge the water exclusion on its own.
- **Fix** (`satellite/built_up.py`): added `compute_mndwi()` (Green
  vs SWIR, not NIR -- specifically counters NDBI's own SWIR
  dependence, the standard remote-sensing fix for this exact
  confusion) and a minimum-brightness gate (sum of red+green+nir+
  swir16) that excludes near-zero-reflectance pixels outright, since
  no index threshold can be trusted there regardless. Real urban
  pixels checked comfortably clear the brightness floor (6,000-9,000+
  vs. the 300 floor; problem pixels summed 150-280).
- **Verified for real, twice** (the diagnostic session, then again on
  a fresh production CLI run of the same scene): water pixels wrongly
  flagged as built-up dropped from 58,572 to 2,276 (a 96% reduction),
  with real urban brightness far above the floor (no measurable loss
  of real coverage). `enderata satellite-builtup` (full Luanda AOI) ran
  end-to-end post-fix: 13,591 polygons (was 24,435 on an earlier,
  different-date scene -- not a clean before/after on its own, but
  consistent with removing a large water-classified area). 80/80 tests
  pass (4 new: `compute_mndwi`'s formula, the lagoon case, the
  near-zero-brightness case, and the existing vegetation-exclusion
  test updated for the new required params).
- **Not fully fixed:** the pre-existing, already-documented NDBI
  limitation (bare/cleared soil shares built-up's spectral signature)
  is unrelated and untouched -- the mask still over-classifies at the
  city's non-coastal edges; a residual ~40% of output polygons still
  sit in the AOI's western/coastal third, some of which may be real
  waterfront development and some likely still edge-case false
  positives close to the water-brightness floor. Treat the mask as an
  improved but still coarse density signal, not ground truth (per the
  module's own docstring, unchanged by this fix).

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
- **2026-09-22, scope upgrade -- real per-building segmentation becomes
  possible:** user clarified that current work is non-commercial
  prototyping ("pour le moment ce que je fais est non comercial c'est
  juste du prototypage une fois tout est validé j'achetterai les
  licences qu'il faut"), which the CC BY-NC 4.0 Maxar mosaic's license
  permits. Flagged to the user first: a model trained on NC-licensed
  imagery is itself a likely derivative and would need RE-TRAINING on
  properly licensed imagery before commercial/government use, not just
  a license upgrade -- user's plan already assumes this ("once
  validated, I'll buy the licenses").
  - Verified the Maxar 2017 Luanda mosaic (2.3GB Cloud-Optimized GeoTIFF
    on S3, `oin-hotosm-temp` bucket -- the correct bucket; an initial
    guess at a plausible-looking `oin-hotosm` URL 403'd, this is the
    real one from the API's own `uuid` field) supports fast windowed
    HTTP reads: opens in ~1.5s, a 200x200px crop in ~0.6s. A real
    600x600px true-colour crop, visually reviewed, confirmed genuine
    Luanda street-level detail (individual buildings, cars, a
    roundabout) at 0.5m/pixel.
  - New `ml/maxar_dataset.py`: tiles the real Luanda AOI into
    512x512px (256m x 256m) patches -- 2037 total patches cover the
    whole municipality -- fetches each via one shared COG handle (not
    reopened per patch) and rasterizes the REAL polygon footprints
    (not buffered points -- at 0.5m/pixel a building's actual shape
    matters) that overlap each patch. Verified for real: 40 patches
    built in 7.4s (2037 at that rate would take ~6 minutes), 34/40
    contain at least one real building, mean 7.1% positive pixels.
    Visually sanity-checked side-by-side (true colour vs. label
    overlay) on the patch with the most coverage: the rasterized
    footprints trace individual rooftops accurately -- this is genuine
    per-building segmentation ground truth, not the coarser per-pixel
    density label `ml/dataset.py`'s Sentinel-2 pipeline produces.
  - 5 new unit tests for the pure tiling/rasterization logic (2 bugs
    caught and fixed were in the TESTS themselves -- wrong pixel-row
    math for a 1m/pixel test grid copied from a 10m/pixel test without
    adjusting coordinates, and checking the wrong array index -- not in
    `maxar_dataset.py`, confirmed by direct debugging before assuming
    either way). 65/65 tests passing.
- **2026-09-22, both pipelines feed real models, precision
  prioritized** (user: "les deux amillente lais priviligie la
  precision"): built a shared U-Net (`ml/model.py`, 4-level encoder/
  decoder, ~7.8M params, verified with a real forward+backward pass on
  the GPU: batch of 4 at 512x512x3, 3.06GB peak VRAM) and a generic
  training loop + spatial (not random) train/val split (`ml/train.py`),
  used by both `ml/train_sentinel.py` and `ml/train_maxar.py` (local
  research scripts, not part of the add-on CLI).
- **Real, iterative loss-function debugging** (not guessed, each step
  verified against real per-pixel predictions before moving on):
  1. Plain BCE+Dice, no class-imbalance handling: Sentinel-2 training
     (131 crops, ~1.3% positive pixels) collapsed to predicting
     background on literally every pixel of every validation crop
     (confirmed by inspecting real predictions, not just the loss
     curve) -- val IoU stuck at exactly 0.3333 for 30 straight epochs,
     which turned out to itself be a metric artifact (see below).
  2. Added `pos_weight` (real negative:positive ratio, 65.15) to BCE:
     overcorrected to predicting positive on ~97% of pixels --
     confirmed by inspecting real predictions again.
  3. sqrt-dampened `pos_weight` (8.07): still collapsed to all-negative
     on a fresh run -- the tiny 131-crop Sentinel-2 dataset proved
     highly sensitive to random init either way.
  4. Switched to focal loss (Lin et al. 2017, per-pixel modulation
     instead of one global scalar): on Maxar (425-2037 training
     patches, ~7% positive pixels -- much less extreme imbalance and
     far more data than Sentinel-2's 131 crops), this produced genuine,
     non-collapsed learning.
  - **Separately found and fixed a real bug in the training loop
    itself, not the loss:** the checkpoint-saving criterion averaged
    IoU per-batch, which let a batch with zero true positives count as
    a "free" IoU=1.0 regardless of size -- an epoch with real_recall
    =0.0 (finds nothing) scored *better* than one with real_recall
    =0.31 (finds real buildings) purely from batch composition. Fixed
    by aggregating tp/fp/fn across the WHOLE validation set before
    computing IoU (mathematically sound, can't be gamed the same way);
    also added real recall/precision (not just IoU) to every epoch's
    printed output specifically because IoU alone couldn't be trusted
    to distinguish genuine learning from collapse at this class
    imbalance.
- **Real finding after a full 25-epoch Maxar run (500 patches, this
  fix + focal loss): a "large structure" bias, not genuine house
  detection.** Aggregate validation metrics looked like real progress
  (best IoU 0.089, recall 13.1%, precision 21.8%, non-zero true
  positives confirmed on the full validation set: 23,238 tp). But
  visually inspecting the single validation patch with the model's
  *best* per-patch recall (81%) showed the "detection" was one large,
  distinctively-shaped structure (a water tank/reservoir, visually
  confirmed) -- every ordinary small house rooftop in the same image,
  clearly visible in the true-colour crop, was missed entirely (no
  prediction at all). The aggregate numbers are likely dominated by a
  small number of large, easy-to-segment structures rather than
  reflecting real generalization to typical Luanda housing, which is
  the actual target. This was caught ONLY by looking at a real
  prediction image side-by-side with ground truth, not from any
  aggregate metric -- a second confirmation (after the checkpoint-
  criterion bug above) that these metrics alone are not trustworthy at
  this data scale without a visual check.
- **2026-09-22, response: more training data, same source** (user:
  "télécharge moi des [images] plus visible et plus correcte", then
  clarified: more Maxar patches, same source, to fight the bias with
  more/more-varied real examples). Searched OpenAerialMap across all of
  Angola for a better/newer/different imagery source first -- found
  none for Luanda specifically (only drone captures around Kinshasa/DRC
  and a 2019 Kinshasa-Brazzaville Maxar mosaic, neither relevant).
  Rebuilt the training set with all 2037 available patches (was 500)
  and retrained: best_val_iou=0.2272 (up from 0.089), recall 34.0%,
  precision 40.7% after 25 epochs -- looked like real progress again.
- **2026-09-22, real root cause found: NOT a "large structure" model
  bias -- OSM's building coverage itself is too sparse to train
  against.** A second visual check (this time on the TOP-recall
  patches from the 2037-patch run, not just one) showed the same
  pattern as before, just with more examples: dense residential blocks
  with dozens of real rooftops clearly visible in the true-colour crop,
  but the ground-truth mask marking only ONE large rectangular
  structure as positive -- every ordinary house in frame was simply
  never labelled, not missed by the model. Traced this to
  `ml/maxar_dataset.py`'s label source, `ingestion/osm_buildings.py`'s
  `load_osm_building_footprints` (OSM's volunteer-mapped building
  layer) -- median recall across validation patches that DO contain
  real buildings was only 0.151, consistent with most houses having no
  positive label to learn from at all. More Maxar patches couldn't fix
  this: the bottleneck was label density, not imagery volume, so the
  500-patch and 2037-patch runs hit the same ceiling for the same
  reason.
- **2026-09-22, fix: switched the label source to Google Open
  Buildings (merged with Microsoft Building Footprints + OSM,
  deduplicated), user's explicit choice after being shown this
  finding.** Built `ingestion/open_buildings.py` (was a stale,
  never-executed stub assuming pre-downloaded local tiles) against
  VIDA's combined dataset on Source Cooperative
  (`data.source.coop/vida/google-microsoft-osm-open-buildings`,
  by-country GeoParquet) -- a DIFFERENT repo from the one investigated
  and shelved in the "Sovereign building/road detection model" section
  below (`cholmes/google-open-buildings`, plain Google-only, hit a
  broken S3 endpoint + rate-limiting). This VIDA mirror worked
  cleanly: plain HTTPS range reads, no auth, no rate-limiting
  encountered even under heavy use. Verified real coverage gap: ~861K
  candidate buildings in Luanda's AOI bounding box (843K Google-
  sourced, 18K Microsoft, 189 OSM-only after dedup) vs. OSM alone's
  7,508 -- roughly two orders of magnitude denser, as expected for an
  ML-detected layer over volunteer mapping in an area with heavy
  informal (musseque) housing.
  - Practical access notes for future reference: an exact `ST_Intersects`
    polygon clip against the remote (non-indexed) whole-country table
    pushed a query from ~48s to an estimated several HOURS -- switched
    to a bounding-box-only filter (precise enough here, since patch
    tiling already clips per-patch downstream). A plain single-stream
    `curl` full-file download stalled at ~15KB/s (throttled); a
    16-way parallel HTTP range-request download with per-chunk size
    verification and automatic retry completed the 1.64GB file in
    under a minute and caught a real silent-truncation bug (a naive
    first attempt concatenated chunks without verifying sizes first,
    producing a corrupt file ~178MB short with no error until DuckDB
    failed to find the parquet footer).
  - Re-rasterized the ALREADY-fetched 2037 Maxar RGB patches against
    the new labels (no need to re-fetch imagery, only labels changed):
    12.7x more positive pixels (179.7M vs 14.1M). Retrained from
    scratch, same architecture/loss (focal, 25 epochs): **best_val_iou
    =0.6098** (epoch 21), a ~2.7x improvement over the OSM-labeled
    2037-patch run's 0.2272, and no longer plateaued after a handful of
    epochs -- e.g. recall 75.4%/precision 76.1% at the best checkpoint.
  - Visually re-verified on a RANDOM sample of validation patches (not
    cherry-picked top-N, learning from the earlier false confidence):
    301/306 val patches now contain real buildings (was 104/306),
    median recall=0.757 / median precision=0.771 across that random
    sample (was median recall=0.151). Prediction images now trace
    individual house rooftops across whole dense blocks, matching
    ground truth's actual shapes -- not one blob. The large-structure
    bias is resolved; this is genuine building-level detection.
- **2026-09-22, CLI integration** (user: "intègre le au CLI"). Asked
  first whether this meant the add-on's shipped Docker image or a
  local-only command, given torch (multi-GB) isn't in `requirements.txt`
  and the checkpoint is CC BY-NC-derived -- user chose local-only.
  Added `ml/predict_buildings.py` (tiles the AOI, runs the trained
  U-Net per patch, vectorizes detections to a GeoJSON FeatureCollection)
  and `enderata detect-buildings-ml` (new `cli.py` subcommand, lazy
  `import torch` inside the function with a clear install-instructions
  error if missing, `FileNotFoundError`-style clear error if the
  checkpoint path doesn't exist). Deliberately NOT added to
  `requirements.txt`/the server/viewer -- stays a local, optional CLI
  command only. Verified end-to-end against real data: `--radius-km 0.5
  --max-patches 4` produced 95 real building polygons, valid GeoJSON,
  real Luanda coordinates. 73/73 existing tests still pass (no
  regression). Documented in DOCS.md, including correcting two now-
  stale notes there claiming `open_buildings.py` was still unwired.
- **Not done yet:** decide whether Sentinel-2's per-pixel classifier is
  worth pursuing further given its data-scarcity problem (131 crops
  from one scene) or should be deprioritized (could also be re-run
  against Open Buildings labels rasterized onto its per-pixel grid,
  not yet tried); evaluation against the NDBI/NDVI baseline; server
  route / viewer button for `detect-buildings-ml` (CLI-only so far);
  still bound by the Maxar imagery's CC BY-NC 4.0 license (prototyping/
  local use only, see module docstrings) until re-trained on properly
  licensed imagery -- not usable for the distributed commercial
  product as-is.

### Nationwide expansion (all of Angola) — 2026-09-22

- **User: "okay je veux le faire sur toute l'Angola."** Clarified scope
  first (3 very different things share that phrase, with very
  different feasibility): ML building detection (blocked -- Maxar
  imagery only exists for Luanda, already confirmed); Open Buildings
  addressing (feasible today, clean license, no imagery needed);
  Sentinel-2 built-up mask (feasible today, global coverage). User
  picked the latter two.
- **`aoi.py` generalized**: new `load_aoi(place_query: str)` (any real
  place via OSM/Nominatim geocoding), `load_luanda_aoi()` kept as a
  thin wrapper -- zero breaking change for existing callers.
- **`ingestion/open_buildings.py` extended**: new
  `load_open_buildings_points()` (footprint polygons collapsed to
  centroids, reshaped to match `osm_buildings.py::load_osm_buildings`'s
  columns) as a drop-in alternative building source. Also added
  `clip_to_polygon=True` (default) to `load_open_buildings()` itself --
  the bbox-only candidate set from the remote query is now clipped
  locally to the real AOI polygon with geopandas' vectorized
  `intersects` (fast, sub-seconds-to-seconds even at 800K+ candidates,
  since it's no longer fighting the remote table's lack of a spatial
  index) before being handed to callers that need real precision (like
  addressing), while ML training's patch-tiled rasterization can still
  opt out (`clip_to_polygon=False`) since it re-filters per patch
  anyway.
- **`real_addresses.py` extended**: new `building_source` param
  ("osm" default, unchanged behaviour; "open_buildings" new). New CLI
  flags: `--place` (satellite-builtup/estimate-addresses/real-addresses)
  and `--building-source` (real-addresses only). `duckdb>=1.0` added to
  `requirements.txt`/`pyproject.toml` (ships in the add-on now -- Open
  Buildings has a clean license, unlike Maxar, and duckdb is a small
  compiled wheel, unlike torch).
- **Verified for real, not just unit tests:**
  - `enderata satellite-builtup --place "Huambo, Angola"` ran fully
    end-to-end: real Sentinel-2 scene (S2A_33LWE_20260922, 0% cloud),
    15,392 built-up polygons, real Huambo coordinates (~15.9°E/-11.4°N,
    nowhere near Luanda's ~13.2°E/-8.8°N) in the output GeoJSON.
  - `load_aoi("Huambo, Angola")` + `load_open_buildings_points()`
    called directly: 1,182,378 real buildings for the whole Huambo
    province in 97s (larger area than Luanda, hence slower than
    Luanda's earlier 3.3s).
  - `enderata real-addresses --building-source open_buildings` (full
    CLI path, needs OSM streets too) could NOT be verified end-to-end
    live: `osm_streets.py`'s Overpass POST fetch hit repeated
    `ConnectTimeout`s in this environment (curl and a bare `requests.post`
    to the same endpoint both succeeded independently, so likely a
    transient/large-payload-specific network issue here, not a code
    bug -- `osm_streets.py` itself is unmodified this session and the
    same failure would hit the existing `osm` building source too).
    77/77 unit tests pass, including new ones for the actually-testable
    pure logic (`_footprints_to_points`, invalid `building_source`
    fails fast before any network call).
  - `"Lobito, Angola"` failed to geocode to a polygon via Nominatim
    (`TypeError: ... did not geocode ... to a (Multi)Polygon`) --
    smaller places may need a more specific query string; not every
    Angolan place name has a Nominatim boundary polygon, a real data
    gap outside this project's control, not a bug.
- **Not done yet:** confirm `real-addresses --building-source
  open_buildings` end-to-end once Overpass connectivity is reliably
  available; district/country-code defaults are still hardcoded
  ("AO"/"LUA") -- callers must pass `--district` explicitly for any
  other place; no per-place default district-code lookup table exists.

### Nationwide basemap + viewer place selection — RESOLVED 2026-09-26

- **User, resuming after a session gap: "il s'agissait de faire le
  system sur tout l'angola et de télécharger les cartes et images
  gps."** Investigating what was actually left undone (git history was
  clean/committed up to the water-mask fix above) surfaced two real
  gaps: the self-hosted vector basemap was still clipped to Luanda
  (`tiles/luanda.mbtiles`, 696KB) even though the addressing/satellite
  pipelines had already gone nationwide; and a raw Sentinel-2 archive
  covering the whole country (166.9GB, `ml_data/sentinel2_angola`, 1240
  MGRS tiles' worth of band files) had been downloaded in an earlier,
  never-committed session (found via a leftover scratch script,
  `download_angola_sentinel2.py`) but never wired into anything.
- **Basemap**: regenerated with the exact same cached Planetiler build
  and Geofabrik OSM extract as the original Luanda-only tileset, just
  without the `--bounds` clip -- `tiles/angola.mbtiles`, 154MB,
  298,207 tiles, same zoom range (0-14) and vector layer set (all
  already styled in `map.js`, no new unstyled-layer regression). Old
  file removed, `tileserver.py`/`server.py` point to the new one.
- **Satellite imagery, explicit decision with the user:** presented
  three real options -- fetch-on-demand per place (reuses the existing,
  already-verified Sentinel-2 pipeline, no pre-processing); read the
  166.9GB local archive as a cache with a live fallback; or build a
  genuine pre-rendered national raster tile pyramid from that archive
  (the "photo equivalent" of the vector basemap, but far more
  engineering and still not small -- estimated hundreds of MB to a few
  GB after compression, against this project's stated preference for a
  small self-hosted file). **User chose fetch-on-demand.** The 166.9GB
  archive is therefore NOT wired into the shipped product -- it stays
  local, gitignored (`ml_data/`), useful only as potential ML training
  data if a future session revisits nationwide model training, per its
  original download-script docstring's now-abandoned intent (transfer
  to HA's storage for offline use). Not deleted, since the user didn't
  ask to delete it, but flagged here as unused so a future session
  doesn't assume it's load-bearing.
- **Viewer wiring**: the CLI already supported `--place`
  (`aoi.py::load_aoi`) since the original nationwide-expansion work
  above, but the web viewer (the add-on's actual UI) was still
  hardcoded to `LUANDA_CENTRE` with no way to select another place.
  Added a "Place" panel (place name, district code, building-source
  dropdown) that feeds `place`/`district_code`/`building_source` into
  the existing `/api/load-satellite`, `/api/estimate-addresses`,
  `/api/real-addresses` POST bodies; `server.py`'s own `_resolve_aoi`
  extended to mirror `cli.py`'s (place -> `load_aoi`, radius_km ->
  bbox override, otherwise Luanda default -- unchanged priority order).
- **Verified for real**, not just unit tests: `/api/load-satellite`
  called directly with `{"place": "Huambo, Angola"}` through a real
  locally-run instance of the actual Flask app returned real
  Huambo-region bounds (~14.8-16.6°E / -13.8 to -11.4°N) and a real
  Sentinel-2-derived built-up mask (22,589 polygons) -- not Luanda's.
  `/api/real-addresses` called with an empty body (the pre-existing
  default path) returned the exact same numbers as the last verified
  Luanda run (40,082 streets, 7,508 buildings) -- confirms the
  country_code/district_code refactor (from hardcoded to
  request-body-driven) is a true no-op when no place is given.
  91/91 unit tests pass (2 updated for the new nationwide tileset
  bounds, no logic change needed elsewhere). Test server process
  confirmed stopped afterward (`taskkill`), no leftover listener on
  the test port.
- **Not done yet:** no automatic recentring of the map itself when a
  place is typed (the existing per-action `fitBounds` behaviour just
  naturally lands on whatever place was requested once a button is
  clicked) -- a dedicated "go to place" button/route was considered and
  deliberately left out to keep this change minimal, per the user's
  "on-demand" choice; still no per-place default district-code lookup
  (same known gap as the original nationwide-expansion entry above).

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
