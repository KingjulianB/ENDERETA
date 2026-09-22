"""Covers two things added 2026-09-22 alongside real OSM building
ingestion: run_pipeline() carrying optional building_type/
osm_street_name/osm_housenumber through to AddressedBuilding when
present, and staying backward-compatible (all None) when absent -- plus
a regression test for a real bug hit while building this: geopandas
silently turned a Python None into a float NaN when a GeoDataFrame
column was built from a plain list mixing None and strings, so
run_pipeline() must normalize NaN to None itself rather than trust the
input.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from enderata.pipeline import run_pipeline

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic_sample"


def _load_fixture_streets():
    return gpd.read_file(FIXTURE_DIR / "streets.geojson")


def _buildings_with_attrs():
    # b1 carries real values; b2's osm_street_name is a real NaN float
    # (not Python None) -- reproduces the exact bug found in
    # ingestion/osm_buildings.py's output.
    return gpd.GeoDataFrame(
        {
            "building_id": ["b1", "b2"],
            "building_type": ["house", "warehouse"],
            "osm_street_name": ["Rua da Missao", float("nan")],
            "osm_housenumber": ["12", None],
        },
        geometry=gpd.points_from_xy([15.737, 15.738], [-12.7751, -12.7751]),
        crs="EPSG:4326",
    )


def test_building_attrs_are_carried_through_when_present():
    streets = _load_fixture_streets()
    result = run_pipeline(_buildings_with_attrs(), streets, "AO", "LUA")
    by_id = {item.building_id: item for item in result}

    assert by_id["b1"].building_type == "house"
    assert by_id["b1"].osm_street_name == "Rua da Missao"
    assert by_id["b1"].osm_housenumber == "12"


def test_building_attrs_normalize_nan_to_none():
    streets = _load_fixture_streets()
    result = run_pipeline(_buildings_with_attrs(), streets, "AO", "LUA")
    by_id = {item.building_id: item for item in result}

    assert by_id["b2"].building_type == "warehouse"
    assert by_id["b2"].osm_street_name is None  # was float('nan') in the input
    assert by_id["b2"].osm_housenumber is None


def test_building_attrs_default_to_none_when_columns_absent():
    buildings = gpd.read_file(FIXTURE_DIR / "buildings.geojson")
    streets = _load_fixture_streets()
    result = run_pipeline(buildings, streets, "AO", "LUA")

    assert all(item.building_type is None for item in result)
    assert all(item.osm_street_name is None for item in result)
    assert all(item.osm_housenumber is None for item in result)
