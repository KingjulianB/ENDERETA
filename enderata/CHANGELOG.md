# Changelog

## Unreleased
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
