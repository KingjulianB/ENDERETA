"""Orchestrates addressing from REAL building footprints: real OSM
buildings + real OSM streets -> run_pipeline(). No satellite fetch
needed -- unlike estimate_addresses.py, this path doesn't depend on
the Sentinel-2 built-up mask at all.

OSM's building coverage in Luanda is real but volunteer-mapped and
incomplete (749 buildings in the default 1.6km-radius AOI, verified
2026-09-22 -- see ingestion/osm_buildings.py), not exhaustive like a
satellite-derived dataset (Google Open Buildings) would be. This is
the preferred building source where OSM has mapped coverage; gaps
still fall back to estimate_addresses.py's grid-sampled points, or (a
planned follow-up, not yet wired in -- see discrepancies.md) Google
Open Buildings for areas OSM hasn't mapped.

Took a bbox tuple until 2026-09-22, when `aoi.py` added a real Luanda
boundary polygon -- switched to take that polygon directly (passed
straight through to osm_streets.py/osm_buildings.py's own
polygon-based fetches, no bbox rectangle in between).
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from enderata.ingestion.osm_buildings import load_osm_buildings
from enderata.ingestion.osm_streets import load_osm_streets
from enderata.numbering.sequence import SequenceProvider
from enderata.pipeline import AddressedBuilding, run_pipeline


@dataclass(frozen=True)
class RealAddressingResult:
    addressed: list[AddressedBuilding]
    streets_gdf: gpd.GeoDataFrame
    n_streets: int
    n_osm_buildings: int
    n_addressed: int


def run_real_addressing(
    aoi: BaseGeometry,
    country_code: str,
    district_code: str,
    max_distance: float | None = 100.0,
    sequence_provider: SequenceProvider | None = None,
) -> RealAddressingResult:
    """Fetch real OSM buildings and real OSM streets for `aoi` (a
    shapely Polygon/MultiPolygon, EPSG:4326) and run the numbering
    pipeline on them.

    `max_distance` (metres) drops real buildings too far from any
    street to plausibly belong to it -- defaults wider than
    estimate_addresses.py's since real building placement is less
    regular than a fixed sampling grid. `sequence_provider` is passed
    straight through to run_pipeline() -- see its docstring.
    """
    streets_gdf = load_osm_streets(aoi)
    buildings_gdf = load_osm_buildings(aoi)

    addressed = run_pipeline(
        buildings_gdf,
        streets_gdf,
        country_code,
        district_code,
        max_distance=max_distance,
        sequence_provider=sequence_provider,
    )

    return RealAddressingResult(
        addressed=addressed,
        streets_gdf=streets_gdf,
        n_streets=len(streets_gdf),
        n_osm_buildings=len(buildings_gdf),
        n_addressed=len(addressed),
    )
