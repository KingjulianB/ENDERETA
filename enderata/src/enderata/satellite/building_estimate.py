"""Generate estimated building points within a Sentinel-2 NDBI/NDVI
built-up mask, for districts with no real building-footprint data.

This is NOT real building detection -- Sentinel-2 is 10m/pixel and
cannot resolve individual structures (see built_up.py's own
docstring). It's a deterministic grid sample of the built-up area,
used only so the numbering pipeline (street assignment + house
numbering, see pipeline.py) has *something* concrete to run against
for a pilot district lacking Open Buildings/imagery-derived
footprints. Every output row carries `building_id` prefixed `est-` so
downstream consumers (viewer, exports) can tell estimated points apart
from real ones -- never present these as verified building locations.
"""

from __future__ import annotations

import math

import geopandas as gpd
from shapely.geometry import Point, shape
from shapely.ops import unary_union


def _built_up_geometry(built_up_feature_collection: dict):
    polygons = [
        shape(f["geometry"])
        for f in built_up_feature_collection["features"]
        if f["properties"].get("built_up")
    ]
    if not polygons:
        return None
    return unary_union(polygons)


def estimate_building_points(
    built_up_feature_collection: dict,
    spacing_m: float = 60.0,
    max_points: int = 1000,
) -> gpd.GeoDataFrame:
    """Sample a regular grid of points (spacing `spacing_m` metres,
    converted to degrees at the built-up area's own latitude) that
    fall inside the built-up mask.

    `max_points` bounds the output size regardless of how large the
    built-up area turns out to be: `street_assignment.py`'s
    nearest-street search is O(buildings x streets) with no spatial
    index, so an uncapped grid over a real city-scale built-up area
    (tens of km^2) produces tens of thousands of points and makes
    run_pipeline() impractically slow for an interactive button. If
    the raw grid exceeds `max_points`, it's deterministically
    downsampled by even stride (not randomly), so results stay
    reproducible for a given scene/mask/spacing.

    Returns a GeoDataFrame with `building_id` (e.g. "est-00001") and
    Point `geometry` in EPSG:4326, shaped for
    `enderata.pipeline.run_pipeline`. Empty (but correctly shaped) if
    the mask has no built-up polygons.
    """
    built_up = _built_up_geometry(built_up_feature_collection)
    if built_up is None or built_up.is_empty:
        return gpd.GeoDataFrame({"building_id": [], "geometry": []}, geometry="geometry", crs="EPSG:4326")

    west, south, east, north = built_up.bounds
    centre_lat = (south + north) / 2
    lat_step = spacing_m / 111_000.0
    lon_step = spacing_m / (111_000.0 * max(math.cos(math.radians(centre_lat)), 0.01))

    points: list[Point] = []
    lat = south
    while lat <= north:
        lon = west
        while lon <= east:
            candidate = Point(lon, lat)
            if built_up.contains(candidate):
                points.append(candidate)
            lon += lon_step
        lat += lat_step

    if len(points) > max_points:
        stride = math.ceil(len(points) / max_points)
        points = points[::stride]

    building_ids = [f"est-{i:05d}" for i in range(len(points))]
    return gpd.GeoDataFrame(
        {"building_id": building_ids, "geometry": points},
        geometry="geometry",
        crs="EPSG:4326",
    )
