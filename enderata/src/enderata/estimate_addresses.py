"""Orchestrates the "estimate addresses" feature: real OSM streets +
Sentinel-2 built-up-derived building points -> run_pipeline().

For a district (like the current Luanda pilot) with no real building-
footprint source yet (see discrepancies.md "Sovereign building/road
detection model" and "Real Luanda AOI boundary"), this is the only
concrete building input available today. Every output building comes
from `building_estimate.py`'s grid sample, not a verified footprint --
callers (CLI, server route, viewer) must keep presenting this as an
estimate, not ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd

from enderata.ingestion.osm_streets import load_osm_streets
from enderata.pipeline import AddressedBuilding, run_pipeline
from enderata.satellite.building_estimate import estimate_building_points
from enderata.satellite.pipeline import BuiltUpResult, detect_built_up_area


@dataclass(frozen=True)
class EstimatedAddressingResult:
    addressed: list[AddressedBuilding]
    built_up: BuiltUpResult
    streets_gdf: gpd.GeoDataFrame
    n_streets: int
    n_estimated_buildings: int
    n_addressed: int


def run_estimated_addressing(
    bbox_wgs84: tuple[float, float, float, float],
    country_code: str,
    district_code: str,
    spacing_m: float = 60.0,
    max_points: int = 1000,
    max_distance: float | None = 60.0,
) -> EstimatedAddressingResult:
    """Fetch a real Sentinel-2 built-up mask and real OSM streets for
    `bbox_wgs84`, sample estimated building points inside the mask,
    and run the numbering pipeline on them.

    `max_distance` (metres) drops estimated points too far from any
    real street to plausibly belong to it -- default matches
    `spacing_m` so isolated points at the built-up area's edges don't
    get spuriously addressed.
    """
    built_up = detect_built_up_area(bbox_wgs84)
    streets_gdf = load_osm_streets(bbox_wgs84)
    buildings_gdf = estimate_building_points(
        built_up.feature_collection, spacing_m=spacing_m, max_points=max_points
    )

    addressed = run_pipeline(
        buildings_gdf, streets_gdf, country_code, district_code, max_distance=max_distance
    )

    return EstimatedAddressingResult(
        addressed=addressed,
        built_up=built_up,
        streets_gdf=streets_gdf,
        n_streets=len(streets_gdf),
        n_estimated_buildings=len(buildings_gdf),
        n_addressed=len(addressed),
    )
