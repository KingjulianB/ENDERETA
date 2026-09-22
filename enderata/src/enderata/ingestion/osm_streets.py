"""Fetch OpenStreetMap street geometries for the ENDERETA AOI via osmnx.

NOT exercised against real data or network in this session -- verify
against a real Luanda extract before relying on it.
"""

from __future__ import annotations

import geopandas as gpd
import osmnx as ox
from shapely.geometry.base import BaseGeometry


def load_osm_streets(aoi: BaseGeometry) -> gpd.GeoDataFrame:
    graph = ox.graph_from_polygon(aoi, network_type="drive")
    _, edges = ox.graph_to_gdfs(graph)
    edges["source"] = "osm"
    return edges
