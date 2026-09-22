"""Real building footprints from Google Open Buildings, merged with
Microsoft Building Footprints and OSM and deduplicated, via VIDA's
combined dataset on Source Cooperative -- a satellite/ML-derived
building layer, not volunteer-mapped like `osm_buildings.py`'s source.

Why this exists: `osm_buildings.py`'s own docstring notes OSM's
coverage is incomplete, not exhaustive. Verified 2026-09-22 against
this project's actual problem (the Maxar building-segmentation model
training on OSM-derived labels was only learning to find the handful
of large structures OSM happens to have digitized, missing the vast
majority of ordinary houses visible in the imagery but never mapped in
OSM): a bbox query against Luanda's real AOI bounding box returned
~843K Google-sourced candidate buildings vs. OSM's 7,508 for the same
area (`osm_buildings.py`'s count) -- roughly two orders of magnitude
denser coverage, the expected result of an ML-detected dataset over
volunteer mapping in an area with heavy informal (musseque) housing.

Distribution: public GeoParquet on Source Cooperative
(https://data.source.coop/vida/google-microsoft-osm-open-buildings/),
one file per country (ISO3 code), queried with DuckDB's httpfs+spatial
extensions over plain HTTPS range reads -- no S3 auth, no API key.
Confirmed working 2026-09-22 (`curl -I` on the AGO file: 200 OK,
Accept-Ranges: bytes, no auth headers needed). An earlier attempt at
the original Google-only mirror (`data.source.coop/cholmes/google-
open-buildings`) hit a broken non-standard S3 endpoint and HTTPS
rate-limiting -- see discrepancies.md "Own neural network for built-up
detection". This VIDA mirror, hosted the same way but a different
repo/dataset, worked cleanly with no rate-limiting encountered.

License: per-row via `bf_source` ("google" -> CC-BY-4.0, "microsoft"
-> ODbL, "osm" -> ODbL) -- all clean, unlike the Maxar imagery these
footprints get rasterized onto for ML training labels (that imagery,
not this data, is the NC-licensed piece).
"""

from __future__ import annotations

import geopandas as gpd
import shapely.wkb
from shapely.geometry.base import BaseGeometry

OPEN_BUILDINGS_BASE_URL = "https://data.source.coop/vida/google-microsoft-osm-open-buildings/geoparquet/by_country"


def _duckdb_connection():
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


def load_open_buildings(
    aoi: BaseGeometry,
    country_iso: str = "AGO",
    source_path: str | None = None,
) -> gpd.GeoDataFrame:
    """Real building footprints intersecting `aoi` (a shapely Polygon/
    MultiPolygon, EPSG:4326), from the combined Google/Microsoft/OSM
    dataset. Filters on the file's own `bbox` struct first (cheap
    rejection) then `ST_Intersects` against the real AOI polygon (not
    just its bounding box), inside the SQL query -- clipping 800K+
    candidate rows down to the real AOI in the database engine, not
    after pulling everything into Python.

    `source_path` overrides the remote URL with a local file path (a
    pre-downloaded country parquet) -- querying a local file avoids
    re-fetching ~1.6GB over HTTP on every call, which matters for this
    dataset (unlike `osm_buildings.py`'s live Overpass calls) since
    there's no per-AOI remote endpoint, only whole-country files.
    """
    path = source_path or f"{OPEN_BUILDINGS_BASE_URL}/country_iso={country_iso}/{country_iso}.parquet"
    minx, miny, maxx, maxy = aoi.bounds
    con = _duckdb_connection()
    # Bounding-box filter only (no ST_Intersects against the real AOI
    # polygon here) -- verified 2026-09-22 that adding an exact-polygon
    # clip against this remote, non-spatially-indexed table pushed the
    # query from ~48s to an estimated several HOURS (each of the
    # country's ~800K+ rows gets a full geometry-intersection test
    # against the AOI's real, many-vertex polygon, with no index to
    # skip most of them). A bbox-only candidate set is precise enough
    # here: callers that tile the AOI into patches (`ml/maxar_dataset.py`)
    # already filter footprints per-patch, so a few extra buildings just
    # outside the real polygon but inside its bbox have no effect.
    df = con.execute(
        f"""
        SELECT
            bf_source,
            confidence,
            area_in_meters,
            ST_AsWKB(geometry) AS wkb
        FROM read_parquet('{path}')
        WHERE bbox.xmin <= {maxx} AND bbox.xmax >= {minx}
          AND bbox.ymin <= {maxy} AND bbox.ymax >= {miny}
        """
    ).df()

    geometry = [shapely.wkb.loads(bytes(wkb)) for wkb in df["wkb"]]
    building_ids = [f"ob-{source}-{i}" for i, source in enumerate(df["bf_source"])]

    return gpd.GeoDataFrame(
        {
            "building_id": building_ids,
            "geometry": geometry,
            "bf_source": df["bf_source"].values,
            "confidence": df["confidence"].values,
            "area_in_meters": df["area_in_meters"].values,
        },
        crs="EPSG:4326",
    )
