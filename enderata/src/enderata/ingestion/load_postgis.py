"""Write a processed GeoDataFrame to a PostGIS table."""

from __future__ import annotations

import geopandas as gpd
from sqlalchemy.engine import Engine


def load_to_postgis(
    gdf: gpd.GeoDataFrame, table_name: str, engine: Engine, if_exists: str = "append"
) -> None:
    gdf.to_postgis(table_name, engine, if_exists=if_exists, index=False)
