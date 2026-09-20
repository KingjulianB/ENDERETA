# ENDERETA — Day 1 Goals
**Date:** 2026-09-20
**Project:** ENDERETA — national digital addressing system for Angola. This file covers the first session, packaging the Huambo POC as a Home Assistant add-on.
**Purpose of this file:** Written retroactively partway through the session, after `project_log.md`/`discrepancies.md` were set up — it records what this session actually did (checked items) and what's still open going into the next session (unchecked items, which become day2's starting point).

---

## Objective A — Plan the technical foundation from the business plan
- [x] Read `ENDERETA_Business_Plan.pdf`, confirm no existing code in the repo
- [x] Propose architecture (Python + PostGIS pipeline, numbering engine, viewer) and get it validated before writing code (ECC `/plan` workflow)
- [x] Pivot the plan on request: package everything as a Home Assistant add-on instead of a standalone service

**status:** done

---

## Objective B — Scaffold and unit-test the numbering engine
- [x] Permanent postal-ID generator with a MOD 97-10 style check digit
- [x] Street assignment (nearest street, side-of-line detection) and house numbering (odd/even ordering)
- [x] Address formatter, kept separate from the postal ID by design
- [x] `pipeline.py` orchestration + `enderata number-district` CLI
- [x] Synthetic fixture + permanence regression test (identical postal IDs across reruns) + ID/address-separation test — 16/16 tests passing

**status:** done

---

## Objective C — Get the add-on actually building and running on the user's real HA instance
- [x] Fix build.yaml/base-image mismatch (`apt-get: not found`)
- [x] Remove dead `bashio` dependency (404 install URL)
- [x] Fix `pg_ctl` log-permission error
- [x] Fix missing `postgresql-15-postgis-3` package
- [x] Fix OSM tile-policy 403s (removed the raster basemap)
- [x] Bump `config.yaml` version on every fix so HA Supervisor offers an update

**status:** done — add-on now builds and serves the viewer through HA ingress on real hardware (v0.1.4)

---

## Objective D — Repo hygiene
- [x] Initialize git, keep the confidential business-plan PDF out of the public repo
- [x] Push to the user's GitHub repo (`KingjulianB/ENDERETA`)
- [x] Catch and fix an accidental screenshot commit (personal info) — untrack, rewrite history, force-push with explicit confirmation
- [x] Generate a simple icon/logo for the add-on (Pillow, programmatic)

**status:** done

---

## Objective E — Set up cross-session planning docs (this file + project_log/discrepancies/agreed-workflow)
- [x] Create `project_log.md`, `discrepancies.md`, `day1_objectives.md`, `agreed-workflow.md`

**status:** done

---

## Not in scope today (listed so it isn't lost, not forgotten by omission)
- Real Huambo AOI ingestion — deferred, needs the user to supply the district polygon (see `discrepancies.md`)
- Persistent DB-backed postal-ID sequencing — deferred, needs a design decision (see `discrepancies.md`)
- Choosing a compliant basemap provider — deferred, needs a decision (see `discrepancies.md`)
- Wiring `ingestion/load_postgis.py` into the CLI — deferred, not needed until real ingestion is wired in

---

## End-of-day check
| Objective | Status | Blocker (if any) |
|---|---|---|
| A — Plan | Done | none |
| B — Numbering engine | Done | none |
| C — Add-on builds/runs on real HA | Done | none |
| D — Repo hygiene | Done | none |
| E — Planning docs | Done | none |

**Day verdict:** Very productive first session — went from a business-plan PDF and an empty folder to a Home Assistant add-on that actually builds and serves a working (if data-empty) viewer on the user's real hardware, through five real build/runtime bug fixes found from actual HA logs rather than guesswork.

**Notes for next session — pick up in this order:**
1. Get the real Huambo AOI polygon from the user — this unblocks real ingestion and is the biggest lever on making the rest of the work meaningful.
2. Decide the basemap approach (`discrepancies.md` § Compliant basemap).
3. Wire `ingestion/open_buildings.py` + `ingestion/osm_streets.py` + `ingestion/load_postgis.py` into the CLI once real AOI data exists.
4. Decide and implement persistent postal-ID sequencing before numbering anything beyond the fixture.
5. Re-run the permanence regression test against real data once ingestion is wired in — the synthetic-fixture pass is necessary but not sufficient.
