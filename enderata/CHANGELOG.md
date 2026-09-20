# Changelog

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
