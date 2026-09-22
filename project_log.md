# ENDERETA — Project Log

**Read this first.** One page, tables only, no narrative — a running
index of what needs your decision and what's known-broken, so you can
scan it before opening `discrepancies.md` (full technical detail per
item) or the current `dayX_objectives.md` (session-by-session task
tracking). Updated every time a new decision or issue surfaces;
resolved rows move to the bottom "Resolved" table with the answer, not
deleted.

**Reading order:** this file → `discrepancies.md` → `dayX_objectives.md` → `agreed-workflow.md`.

This project also follows ECC's plan-first, confirm-before-code
workflow (see `agreed-workflow.md`) — this doc set adds cross-session
continuity on top of that, it doesn't replace it.

---

## Decisions needed from you

| # | Decision | One-line context | Full detail |
|---|---|---|---|
| 2 | Real Luanda district AOI polygon | Everything built/tested so far (pipeline, CLI, viewer) runs only on a 5-building synthetic fixture, not real Luanda data | `discrepancies.md` § Real Luanda AOI boundary |
| 3 | Persistent postal-ID sequencing design | `pipeline.py` currently sequences IDs by sorting building_id in memory — fine for a closed fixture, not for a growing real dataset | `discrepancies.md` § Persistent postal-ID sequencing |

## Known issues (not decisions — being investigated, no action needed from you yet)

| # | Issue | Status |
|---|---|---|
| 1 | `open_buildings.py` (Google Open Buildings) not wired into the CLI | Data license is clean (CC-BY-4.0/ODbL) but its Source Cooperative hosting needs non-standard S3/GeoParquet access work — see `discrepancies.md` § Sovereign building/road detection model. `osm_streets.py`/`osm_buildings.py` (real OSM data, not this module) ARE wired in as of v0.1.17/0.1.19 |
| 2 | No PostGIS write step in the CLI | `ingestion/load_postgis.py` exists but nothing calls it yet — `number-district` only writes GeoJSON/CSV |
| 3 | No Alembic migrations | Schema created via `Base.metadata.create_all()`; fine for the POC, will need real migrations before the schema can evolve against live data |

## Resolved

| # | Issue | Resolution |
|---|---|---|
| 1 | HA Supervisor build failed: `apt-get: not found` | `build.yaml`'s image name didn't match Supervisor's validation regex, silently fell back to HA's Alpine base. Removed `build.yaml`, hardcoded `FROM python:3.12-slim-bookworm` in the Dockerfile — fixed in add-on v0.1.1 |
| 2 | `bashio` install step 404'd | URL no longer resolves, and nothing in the codebase actually called bashio — removed it; add-on options now read from `/data/options.json` via `jq` — fixed in v0.1.1 |
| 3 | `pg_ctl` failed: "Permission denied" writing `/data/postgres.log` | `/data` is root-owned, only `/data/postgres` was chowned to `postgres`; log now writes inside `${PGDATA}`, `/var/run/postgresql` pre-created for the unix socket — fixed in v0.1.1 |
| 4 | `CREATE EXTENSION postgis` failed: extension not available | Debian's plain `postgis` apt package is client-tools-only; the server extension needs the versioned `postgresql-15-postgis-3` package, now installed alongside it — fixed in v0.1.3 |
| 5 | Every basemap tile 403'd | OpenStreetMap's tile usage policy forbids `tile.openstreetmap.org` in a distributed/packaged app without prior OSMF approval — tile layer removed, viewer auto-fits to GeoJSON on a plain background instead (see open decision #1 above for a real basemap) — fixed in v0.1.4 |
| 6 | Confidential business-plan PDF risk on a public repo | `ENDERETA_Business_Plan.pdf` (marked "Confidential — Not for distribution") kept local-only, added to `.gitignore` before the first push |
| 9 | Viewer showed a blank grey map after the tile fix | Nothing populated `/data/export`; first fix (ship the fixture in the image, v0.1.5) still needed `docker exec`, which failed (`docker: command not found`) since HA's "Terminal & SSH" add-on has no docker socket access. Real fix (v0.1.6): a "Load demo data" button in the viewer calling a new `POST /api/load-demo` route that runs the pipeline server-side — no shell/docker access needed at all |
| 10 | Compliant basemap for the viewer | Self-hosted: `tiles/huambo.mbtiles` (491KB, OpenMapTiles vector tiles, offline-generated with Planetiler from Angola's real Geofabrik OSM extract, clipped to the Huambo AOI) served straight from that SQLite file at `GET /tiles/<z>/<x>/<y>.pbf`, rendered client-side with Leaflet.VectorGrid — no third party tile server, no usage-policy risk. Verified in a real browser (chrome-devtools screenshots), including a real rendering bug caught and fixed (unstyled OpenMapTiles layers fell back to Leaflet's default blue marker style) — fixed in v0.1.13 |
| 7 | Personal screenshot accidentally committed to the public repo | A `git add -A` swept up a screenshot containing browser tabs/local IP; untracked, history rewritten with `git filter-branch`, and force-pushed after explicit user confirmation |
| 8 | Add-on had no icon/logo | Generated a navy map-pin mark with a teal accent (Pillow, programmatic — not a guessed/downloaded asset); `icon.png` + `logo.png` added in v0.1.2 |
| 11 | OSM editor imagery (Bing/Esri/Maxar via user's OSM account) as an imagery source | Ruled out same as NICFI: all three licensed strictly for tracing within an OSM editor, not bulk download/reuse; Maxar's grant to OSM was revoked entirely in July 2023 |
| 12 | Pilot district: Huambo had no usable imagery source at any price point found; user chose to switch entirely | Full pivot to Luanda, 2026-09-22 — real CC-BY 4.0 0.5m/pixel Maxar imagery exists for Luanda via OpenAerialMap (verified via their live API), none for Huambo. `LUANDA_CENTRE`, `tiles/luanda.mbtiles`, `district_code`/`aoi_district` defaults (`LUA`/`luanda`) all updated; re-verified end to end (real Sentinel-2 fetch, real browser basemap check) — caught and fixed a new bug specific to Luanda's AOI (`water_name` vector layer, absent from Huambo's smaller tileset) — fixed in v0.1.16 |
| 13 | Pretrained building-detection model (SpaceNet 6) tried against real Luanda imagery, closed | Hard blocker verified in the winning model's own README: input is SAR-only (4-channel radar), not RGB optical — wrong model family, not fixable by more effort. Also surfaced a broader licensing concern (SpaceNet's training data is CC BY-SA 4.0; weights may carry the ShareAlike obligation regardless of the training code's own Apache 2.0 license). Searched for a non-SpaceNet alternative — none found meeting the bar (optical, building-specific, clearly licensed, well-documented). Decision: stop pursuing a pretrained model; Sentinel-2 NDBI/NDVI remains the sovereignty-aligned answer for now |
| 14 | User asked for a button to assign addresses via the algorithm | Built "Assign addresses (estimated)": rewrote `ingestion/osm_streets.py` (real osmnx/Overpass fetch, was a stale stub), added `satellite/building_estimate.py` (grid-samples estimated building points inside the Sentinel-2 built-up mask, capped at 1000 points — the nearest-street search has no spatial index and an uncapped real-Luanda grid produced 18000+ points), and `estimate_addresses.py` orchestrating both through the existing `run_pipeline()`. New CLI subcommand + server route + viewer button, all verified against real Luanda data end-to-end and in a real browser (999/999 addressed, ~20s). Caught and fixed a real JS/server key-mismatch bug (`count` vs `n_addressed`) via the browser check. Estimated points, not real footprints — v0.1.17 |
| 15 | User asked to test the button at a larger radius, then "take the max radius even if it takes an hour" | Tested via the real button at 4km (16,735 streets, 60s) and directly at 20km (268,753 streets, 897/897 addressed, 675.3s — street assignment's O(buildings x streets) linear scan was the dominant cost, confirmed by re-timing each stage). User then asked to add a spatial index for streets — added `StreetIndex` (shapely STRtree) to `street_assignment.py`, built once per `run_pipeline()` call. Re-verified at the same 20km extract: street assignment dropped to 1.2s, total run to 61.4s (now dominated by real Overpass/Sentinel-2 fetch time, not computation) — v0.1.18 |
| 16 | Asked "what can we add", user picked "real building footprints (Open Buildings)" | Investigated Google Open Buildings: license clean (CC-BY-4.0/ODbL), but Source Cooperative hosting needed non-standard S3 endpoint plumbing that didn't resolve as documented + hit rate-limiting mid-exploration. Found real OSM building footprints already exist for Luanda (osmnx `features_from_bbox`, same mechanism as streets) — 749 real buildings verified. Presented both findings to the user, who chose "OSM first, Google as a complement". Built `ingestion/osm_buildings.py` + `real_addresses.py` + new CLI subcommand/route/viewer button ("Assign addresses (real OSM buildings)", green layer), verified end-to-end (749/749 addressed, ~1.2s, no satellite call) and in a real browser. Google Open Buildings noted as a planned follow-up for gap-filling, not implemented — v0.1.19 |
