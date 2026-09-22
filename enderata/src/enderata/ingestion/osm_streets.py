"""Fetch real OpenStreetMap street geometries for an AOI via osmnx
(Overpass API under the hood) and shape them to match what
`enderata.pipeline.run_pipeline` expects: a GeoDataFrame with
`street_id`, `name`, `geometry` columns.

Verified 2026-09-22 against the real Luanda AOI (bbox_from_center on
LUANDA_CENTRE): 2305 real street edges returned, real Portuguese
street names (UTF-8 verified byte-correct -- an apparent mojibake in
one shell's echo turned out to be a terminal display artifact, not
actual data corruption). ~54% of edges have no OSM `name` tag (normal
for minor/service ways); those fall back to "Unnamed street".

Took a bbox tuple until 2026-09-22, when `aoi.py` added a real Luanda
boundary polygon -- switched to `ox.graph_from_polygon` so streets are
clipped to the actual administrative boundary, not a bbox rectangle
that includes area outside the district (or excludes area inside it,
for a non-square district like Luanda). A bbox tuple still works by
wrapping it with `shapely.geometry.box(*bbox)` before calling.
"""

from __future__ import annotations

import geopandas as gpd
import osmnx as ox
from shapely.geometry.base import BaseGeometry

UNNAMED = "Unnamed street"


def _clean_name(value) -> str:
    if isinstance(value, list):
        return value[0] if value else UNNAMED
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return UNNAMED
    return str(value)


def load_osm_streets(aoi: BaseGeometry) -> gpd.GeoDataFrame:
    """Fetch drivable streets within `aoi` (a shapely Polygon/
    MultiPolygon, EPSG:4326) and return them shaped for `run_pipeline`."""
    graph = ox.graph_from_polygon(aoi, network_type="drive")
    _, edges = ox.graph_to_gdfs(graph)

    streets = gpd.GeoDataFrame(
        {
            "street_id": [f"osm-{i}" for i in range(len(edges))],
            "name": [_clean_name(n) for n in edges["name"]],
            "geometry": edges["geometry"].values,
        },
        crs=edges.crs,
    )
    return streets
