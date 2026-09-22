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
"""

from __future__ import annotations

import geopandas as gpd
import osmnx as ox

UNNAMED = "Unnamed street"


def _clean_name(value) -> str:
    if isinstance(value, list):
        return value[0] if value else UNNAMED
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return UNNAMED
    return str(value)


def load_osm_streets(bbox_wgs84: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Fetch drivable streets within `bbox_wgs84` (west, south, east,
    north) and return them shaped for `run_pipeline`."""
    graph = ox.graph_from_bbox(bbox_wgs84, network_type="drive")
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
