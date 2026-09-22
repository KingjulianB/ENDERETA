"""Real district/province AOI boundaries -- replaces the rough
`bbox_from_center` square used everywhere until 2026-09-22 (see
discrepancies.md "Real Luanda AOI boundary").

Fetched via OSM/Nominatim geocoding (osmnx), the same data ecosystem
already used for streets and buildings. `load_luanda_aoi()` verified
2026-09-22: returns "Luanda, Municipality of Luanda, Luanda Province,
Angola" as a single real Polygon, bounds (13.1732, -8.9208) to
(13.3109, -8.7592) -- an irregular ~15km x 18km shape following the
actual administrative boundary, not a square.

`load_aoi()` generalizes this to any place (2026-09-22, user: "je veux
le faire sur toute l'Angola") -- the addressing/built-up-mask paths
that only ever depended on OSM + Sentinel-2 (both nationwide-covered)
were hardcoded to Luanda's query string for no real reason; the
building-detection U-Net stays Luanda-only regardless, since it
depends on Maxar imagery that only exists there (see discrepancies.md
"Own neural network for built-up detection").
"""

from __future__ import annotations

import osmnx as ox
from shapely.geometry.base import BaseGeometry

LUANDA_QUERY = "Luanda, Angola"


def load_aoi(place_query: str) -> BaseGeometry:
    """Fetch any real place boundary polygon (EPSG:4326) via OSM/
    Nominatim geocoding -- e.g. "Huambo, Angola" or a full province
    name. Raises whatever osmnx/Nominatim raises for a query that
    doesn't resolve (no silent fallback to a guessed bbox)."""
    gdf = ox.geocode_to_gdf(place_query)
    return gdf.geometry.iloc[0]


def load_luanda_aoi() -> BaseGeometry:
    """Fetch the real Luanda municipality boundary polygon (EPSG:4326)."""
    return load_aoi(LUANDA_QUERY)
