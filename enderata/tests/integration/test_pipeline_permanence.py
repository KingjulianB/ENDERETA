"""Integration test on synthetic fixture data (tests/fixtures/synthetic_sample/
-- NOT real Huambo data, see that folder's README).

Exercises the full non-ingestion pipeline (street assignment -> house
numbering -> permanent postal IDs -> address formatting) and enforces
the two guarantees the business plan is built on:

1. Permanence: re-running the pipeline on the same input yields
   identical postal IDs every time.
2. ID/address separation: the postal ID never appears inside the
   human-readable display address.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from enderata.numbering.postal_id import is_valid_postal_id
from enderata.pipeline import run_pipeline

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic_sample"


def _load_fixture():
    buildings = gpd.read_file(FIXTURE_DIR / "buildings.geojson")
    streets = gpd.read_file(FIXTURE_DIR / "streets.geojson")
    return buildings, streets


def test_pipeline_assigns_every_fixture_building():
    buildings, streets = _load_fixture()
    result = run_pipeline(buildings, streets, "AO", "HUA")
    assert len(result) == len(buildings)


def test_generated_postal_ids_are_valid_and_unique():
    buildings, streets = _load_fixture()
    result = run_pipeline(buildings, streets, "AO", "HUA")

    postal_ids = [item.postal_id for item in result]
    assert len(postal_ids) == len(set(postal_ids)), "postal IDs must be unique"
    assert all(is_valid_postal_id(pid) for pid in postal_ids)


def test_postal_ids_are_permanent_across_reruns():
    buildings, streets = _load_fixture()

    first_run = {item.building_id: item.postal_id for item in run_pipeline(buildings, streets, "AO", "HUA")}
    second_run = {item.building_id: item.postal_id for item in run_pipeline(buildings, streets, "AO", "HUA")}

    assert first_run == second_run


def test_display_address_never_contains_the_postal_id():
    buildings, streets = _load_fixture()
    result = run_pipeline(buildings, streets, "AO", "HUA")

    for item in result:
        assert item.postal_id not in item.display_address
