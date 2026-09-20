"""Download and clip Google Open Buildings footprints to the ENDERETA AOI.

Google Open Buildings is distributed as per-S2-cell CSV/GeoJSON tiles.
This module assumes the relevant tiles for the AOI have already been
downloaded locally (see DOCS.md) and simply clips them.

NOT exercised against real data or network in this session -- verify
against an actual Open Buildings tile before relying on it.
"""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry.base import BaseGeometry


def load_open_buildings(aoi: BaseGeometry, tiles_path: str) -> gpd.GeoDataFrame:
    """Load Open Buildings polygons intersecting `aoi` from local tile(s)."""
    combined = gpd.read_file(tiles_path)
    clipped = combined[combined.intersects(aoi)].copy()
    clipped["source"] = "open_buildings"
    return clipped
