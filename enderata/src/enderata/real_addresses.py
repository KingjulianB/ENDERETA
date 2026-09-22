"""Orchestrates addressing from REAL building footprints: real
buildings + real OSM streets -> run_pipeline(). No satellite fetch
needed -- unlike estimate_addresses.py, this path doesn't depend on
the Sentinel-2 built-up mask at all.

Two building sources, chosen via `building_source`:
- "osm" (default, unchanged behaviour): OSM's building coverage is
  real but volunteer-mapped and incomplete (749 buildings in the
  default 1.6km-radius Luanda AOI, verified 2026-09-22 -- see
  ingestion/osm_buildings.py), not exhaustive like a satellite-derived
  dataset would be.
- "open_buildings" (added 2026-09-22, user: "je veux le faire sur
  toute l'Angola"): Google Open Buildings merged with Microsoft
  Building Footprints + OSM (`ingestion/open_buildings.py`), ~861K
  candidate buildings in Luanda's AOI alone vs OSM's 7,508 -- and,
  unlike Maxar imagery (Luanda-only, see discrepancies.md "Own neural
  network for built-up detection"), this dataset covers the whole
  country, so this is the path that actually scales nationwide. No
  address/type tags though (Open Buildings has none) -- every result's
  `building_type` is "other", `osm_street_name`/`osm_housenumber` are
  always None.

Took a bbox tuple until 2026-09-22, when `aoi.py` added a real Luanda
boundary polygon -- switched to take that polygon directly (passed
straight through to osm_streets.py/osm_buildings.py's own
polygon-based fetches, no bbox rectangle in between).
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from enderata.ingestion.open_buildings import load_open_buildings_points
from enderata.ingestion.osm_buildings import load_osm_buildings
from enderata.ingestion.osm_streets import load_osm_streets
from enderata.numbering.sequence import SequenceProvider
from enderata.pipeline import AddressedBuilding, run_pipeline

BUILDING_SOURCES = ("osm", "open_buildings")


@dataclass(frozen=True)
class RealAddressingResult:
    addressed: list[AddressedBuilding]
    streets_gdf: gpd.GeoDataFrame
    n_streets: int
    n_osm_buildings: int
    n_addressed: int
    building_source: str = "osm"


def run_real_addressing(
    aoi: BaseGeometry,
    country_code: str,
    district_code: str,
    max_distance: float | None = 100.0,
    sequence_provider: SequenceProvider | None = None,
    building_source: str = "osm",
) -> RealAddressingResult:
    """Fetch real buildings (source chosen by `building_source`, see
    module docstring) and real OSM streets for `aoi` (a shapely
    Polygon/MultiPolygon, EPSG:4326) and run the numbering pipeline on
    them.

    `max_distance` (metres) drops real buildings too far from any
    street to plausibly belong to it -- defaults wider than
    estimate_addresses.py's since real building placement is less
    regular than a fixed sampling grid. `sequence_provider` is passed
    straight through to run_pipeline() -- see its docstring.
    """
    if building_source not in BUILDING_SOURCES:
        raise ValueError(f"unknown building_source: {building_source!r}, expected one of {BUILDING_SOURCES}")

    streets_gdf = load_osm_streets(aoi)
    if building_source == "osm":
        buildings_gdf = load_osm_buildings(aoi)
    else:
        buildings_gdf = load_open_buildings_points(aoi)

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
        building_source=building_source,
    )
