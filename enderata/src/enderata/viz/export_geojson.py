"""Export processed layers to GeoJSON for the static demo viewer."""

from __future__ import annotations

import geopandas as gpd


def export_geojson(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    gdf.to_crs(epsg=4326).to_file(output_path, driver="GeoJSON")
