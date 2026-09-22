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

import warnings

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
    clip_to_polygon: bool = True,
) -> gpd.GeoDataFrame:
    """Real building footprints intersecting `aoi` (a shapely Polygon/
    MultiPolygon, EPSG:4326), from the combined Google/Microsoft/OSM
    dataset. Filters on the file's own `bbox` struct first (cheap
    rejection, done in SQL) -- NOT `ST_Intersects` against the real AOI
    polygon inside the query: verified 2026-09-22 that pushing an
    exact-polygon clip into this remote, non-spatially-indexed table
    took the query from ~48s to an estimated several HOURS (every one
    of the country's ~800K+ rows gets a full geometry-intersection
    test against the AOI's real, many-vertex polygon, with no index to
    skip most of them).

    `clip_to_polygon` (default True) instead clips the much smaller
    bbox-filtered candidate set to the real `aoi` polygon locally,
    with geopandas' vectorized (shapely 2.0) `intersects` -- fast
    (sub-second to a few seconds even for 800K+ candidates) because
    it's no longer fighting the remote table's lack of a spatial
    index. Set False only when bbox-precision is acceptable and every
    row matters for speed (e.g. `ml/maxar_dataset.py`'s patch-tiled
    training-label rasterization, which re-filters per patch anyway).

    `source_path` overrides the remote URL with a local file path (a
    pre-downloaded country parquet) -- querying a local file avoids
    re-fetching ~1.6GB over HTTP on every call, which matters for this
    dataset (unlike `osm_buildings.py`'s live Overpass calls) since
    there's no per-AOI remote endpoint, only whole-country files.
    """
    path = source_path or f"{OPEN_BUILDINGS_BASE_URL}/country_iso={country_iso}/{country_iso}.parquet"
    minx, miny, maxx, maxy = aoi.bounds
    con = _duckdb_connection()
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

    gdf = gpd.GeoDataFrame(
        {
            "building_id": building_ids,
            "geometry": geometry,
            "bf_source": df["bf_source"].values,
            "confidence": df["confidence"].values,
            "area_in_meters": df["area_in_meters"].values,
        },
        crs="EPSG:4326",
    )
    if clip_to_polygon:
        gdf = gdf[gdf.geometry.intersects(aoi)].reset_index(drop=True)
    return gdf


def load_open_buildings_points(
    aoi: BaseGeometry,
    country_iso: str = "AGO",
    source_path: str | None = None,
) -> gpd.GeoDataFrame:
    """Like `load_open_buildings`, but each footprint collapsed to its
    centroid and reshaped to match `osm_buildings.py::load_osm_buildings`'s
    output columns -- a drop-in alternative building source for
    `real_addresses.py` (2026-09-22, user: "je veux le faire sur toute
    l'Angola" -- OSM's building coverage is real but volunteer-mapped
    and incomplete nationwide, same problem this module was built to
    fix for ML training labels, see the module docstring). Open
    Buildings carries no address/type tags (unlike OSM): `building_type`
    is always "other", `osm_street_name`/`osm_housenumber`/`osm_name`
    are always None."""
    footprints = load_open_buildings(aoi, country_iso=country_iso, source_path=source_path)
    return _footprints_to_points(footprints)


def _footprints_to_points(footprints: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    with warnings.catch_warnings():
        # Same planar-centroid-in-degrees approximation osm_buildings.py's
        # load_osm_buildings() already uses -- negligible distortion at
        # building scale, see that module's docstring.
        warnings.simplefilter("ignore", UserWarning)
        points = footprints.geometry.centroid
    n = len(footprints)
    return gpd.GeoDataFrame(
        {
            "building_id": footprints["building_id"].values,
            "geometry": points.values,
            "building_type": ["other"] * n,
            "osm_street_name": [None] * n,
            "osm_housenumber": [None] * n,
            "osm_name": [None] * n,
        },
        crs=footprints.crs,
    )
