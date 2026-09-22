"""The real Luanda district AOI boundary -- replaces the rough
`bbox_from_center` square used everywhere until 2026-09-22 (see
discrepancies.md "Real Luanda AOI boundary").

Fetched via OSM/Nominatim geocoding (osmnx), the same data ecosystem
already used for streets and buildings. Verified 2026-09-22: returns
"Luanda, Municipality of Luanda, Luanda Province, Angola" as a single
real Polygon, bounds (13.1732, -8.9208) to (13.3109, -8.7592) -- an
irregular ~15km x 18km shape following the actual administrative
boundary, not a square.
"""

from __future__ import annotations

import osmnx as ox
from shapely.geometry.base import BaseGeometry

LUANDA_QUERY = "Luanda, Angola"


def load_luanda_aoi() -> BaseGeometry:
    """Fetch the real Luanda municipality boundary polygon (EPSG:4326)."""
    gdf = ox.geocode_to_gdf(LUANDA_QUERY)
    return gdf.geometry.iloc[0]
