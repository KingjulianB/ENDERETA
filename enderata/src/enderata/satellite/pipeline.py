"""Ties sentinel2.py (fetch) and built_up.py (compute) into one call.

Used by both the CLI (`enderata satellite-builtup`) and the add-on's
`POST /api/load-satellite` route -- kept here once rather than
duplicated in both callers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from enderata.satellite.built_up import (
    built_up_mask,
    compute_ndbi,
    compute_ndvi,
    vectorize_mask,
)
from enderata.satellite.sentinel2 import find_recent_scene, read_bands


def bbox_from_center(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Rough equirectangular bbox (lon_min, lat_min, lon_max, lat_max)
    around (lat, lon) with half-width `radius_km`. Fine at city scale;
    not meant for anything near the poles or very large radii."""
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return (lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta)


@dataclass(frozen=True)
class BuiltUpResult:
    feature_collection: dict
    scene_id: str
    scene_datetime: str
    cloud_cover: float


def detect_built_up_area(
    bbox_wgs84: tuple[float, float, float, float],
    max_cloud_cover: float = 20.0,
    out_size: int = 600,
    ndbi_threshold: float = 0.0,
    ndvi_threshold: float = 0.3,
) -> BuiltUpResult:
    """Fetch the most recent low-cloud Sentinel-2 scene over `bbox_wgs84`
    and return its NDBI+NDVI built-up mask as a GeoJSON FeatureCollection
    plus which real scene it came from (raises RuntimeError if no scene
    is found -- see sentinel2.find_recent_scene)."""
    item = find_recent_scene(bbox_wgs84, max_cloud_cover=max_cloud_cover)
    bands = read_bands(item, bbox_wgs84, out_size=out_size)

    ndbi = compute_ndbi(bands.swir16, bands.nir)
    ndvi = compute_ndvi(bands.nir, bands.red)
    mask = built_up_mask(ndbi, ndvi, ndbi_threshold, ndvi_threshold)
    feature_collection = vectorize_mask(mask, bands.transform, bands.crs)

    return BuiltUpResult(
        feature_collection=feature_collection,
        scene_id=bands.scene_id,
        scene_datetime=bands.datetime,
        cloud_cover=bands.cloud_cover,
    )
