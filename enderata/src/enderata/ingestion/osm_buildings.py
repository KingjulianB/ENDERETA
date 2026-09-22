"""Fetch real building footprints from OpenStreetMap for an AOI via
osmnx (Overpass API under the hood), shaped for
`enderata.pipeline.run_pipeline` (`building_id`, Point `geometry`,
plus `building_type`/`osm_street_name`/`osm_housenumber`/`osm_name`).

Unlike `satellite/building_estimate.py`'s grid-sampled points, these
are REAL, individually-mapped buildings -- but OSM's building coverage
is volunteer-mapped and incomplete, not exhaustive like a satellite-
derived dataset (Google Open Buildings) would be. Verified 2026-09-22
against the real Luanda AOI (bbox_from_center on LUANDA_CENTRE, 1.6km
radius): 749 real buildings (736 polygons + 13 single-node buildings).

Took a bbox tuple until 2026-09-22, when `aoi.py` added a real Luanda
boundary polygon -- switched to `ox.features_from_polygon` so buildings
are clipped to the actual administrative boundary, not a bbox
rectangle. A bbox tuple still works by wrapping it with
`shapely.geometry.box(*bbox)` before calling.

A polygon's centroid is used as its building_id's point location.
Shapely computes this planar even in EPSG:4326 (degrees); for
building-sized polygons the resulting distortion is negligible --
consistent with the equirectangular approximations already used
elsewhere in this codebase (see satellite/pipeline.py's
bbox_from_center), not something this module treats differently.

Building-type classification (added 2026-09-22, user request: "je veux
detecte maisons immeuble et entrepot"): OSM's `building` tag can carry
dozens of values (verified 2026-09-22 against the FULL real Luanda AOI,
7508 buildings: "yes" 4175, "house" 2413, "apartments" 313,
"industrial" 211, "residential" 155, plus ~25 smaller categories --
schools, offices, churches, etc). No building in Luanda's real OSM data
is literally tagged "warehouse" -- "industrial" is used as the closest
real proxy for entrepot/warehouse, a judgment call, not a guess about
whether the data exists (it doesn't, checked). "residential" is
deliberately left as "other" rather than folded into house or
apartment: the tag itself doesn't disambiguate single- vs multi-family,
and guessing would silently mislabel real buildings.
"""

from __future__ import annotations

import warnings

import geopandas as gpd
import osmnx as ox
from shapely.geometry.base import BaseGeometry

_HOUSE_TAGS = {"house", "detached", "semidetached_house", "terrace", "bungalow", "cabin", "static_caravan"}
_APARTMENT_TAGS = {"apartments", "dormitory"}
_WAREHOUSE_TAGS = {"warehouse", "industrial", "storage_tank", "hangar", "factory"}


def classify_building_type(building_tag: object) -> str:
    """Map an OSM `building` tag value to "house" / "apartment" /
    "warehouse" / "other". See module docstring for the exact mapping
    and why ambiguous tags (e.g. "residential") land in "other"."""
    if not isinstance(building_tag, str):
        return "other"
    value = building_tag.lower()
    if value in _HOUSE_TAGS:
        return "house"
    if value in _APARTMENT_TAGS:
        return "apartment"
    if value in _WAREHOUSE_TAGS:
        return "warehouse"
    return "other"


def _clean_str(value: object) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    return str(value)


def load_osm_buildings(aoi: BaseGeometry) -> gpd.GeoDataFrame:
    """Fetch real OSM-mapped buildings within `aoi` (a shapely Polygon/
    MultiPolygon, EPSG:4326) and return them shaped for `run_pipeline`,
    with building-type classification and any existing OSM address
    tags attached (not used to generate addresses -- this project
    assigns its own -- but exposed for comparison/display)."""
    features = ox.features_from_polygon(aoi, tags={"building": True})

    building_ids = [f"osm-{element}-{osm_id}" for element, osm_id in features.index]
    building_types = [classify_building_type(tag) for tag in features.get("building")]
    osm_street_names = [_clean_str(v) for v in features.get("addr:street", [None] * len(features))]
    osm_housenumbers = [_clean_str(v) for v in features.get("addr:housenumber", [None] * len(features))]
    osm_names = [_clean_str(v) for v in features.get("name", [None] * len(features))]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        points = features.geometry.centroid

    buildings = gpd.GeoDataFrame(
        {
            "building_id": building_ids,
            "geometry": points.values,
            "building_type": building_types,
            "osm_street_name": osm_street_names,
            "osm_housenumber": osm_housenumbers,
            "osm_name": osm_names,
        },
        crs=features.crs,
    )
    return buildings
