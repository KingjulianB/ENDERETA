"""Ties sentinel2.py (fetch) and built_up.py (compute) into one call.

Used by both the CLI (`enderata satellite-builtup`) and the add-on's
`POST /api/load-satellite` route -- kept here once rather than
duplicated in both callers.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from enderata.satellite.built_up import (
    built_up_mask,
    compute_mndwi,
    compute_ndbi,
    compute_ndvi,
    vectorize_mask,
)
from enderata.satellite.sentinel2 import find_recent_scene, read_bands
from enderata.satellite.visualize import save_index_heatmap_png, save_true_colour_png


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
    bounds_wgs84: tuple[float, float, float, float]  # (west, south, east, north)
    ndbi_threshold: float
    ndvi_threshold: float


def detect_built_up_area(
    bbox_wgs84: tuple[float, float, float, float],
    max_cloud_cover: float = 20.0,
    max_dimension: int = 2000,
    ndbi_threshold: float = 0.0,
    ndvi_threshold: float = 0.3,
    image_dir: str | None = None,
) -> BuiltUpResult:
    """Fetch the most recent low-cloud Sentinel-2 scene over `bbox_wgs84`
    and return its NDBI+NDVI built-up mask as a GeoJSON FeatureCollection
    plus which real scene it came from (raises RuntimeError if no scene
    is found -- see sentinel2.find_recent_scene).

    `max_dimension` caps the output raster's longer side in pixels
    (both sides scaled down together, preserving the bbox's real aspect
    ratio -- see sentinel2._compute_out_shape) so a large AOI (the full
    real Luanda municipality, ~15km x 18km, not just the original small
    test radius) doesn't blow up memory/processing time; ~10m/pixel
    (Sentinel-2's native resolution) is used up to that cap.

    If `image_dir` is given, also saves `true_colour.png`, `ndbi.png`,
    `ndvi.png` and `mndwi.png` there (georeferenced by `bounds_wgs84` in the
    result, for use as a Leaflet imageOverlay) so a human can inspect
    what the mask was actually computed from and judge whether
    `ndbi_threshold`/`ndvi_threshold` need adjusting.
    """
    item = find_recent_scene(bbox_wgs84, max_cloud_cover=max_cloud_cover)
    bands = read_bands(item, bbox_wgs84, max_dimension=max_dimension)

    ndbi = compute_ndbi(bands.swir16, bands.nir)
    ndvi = compute_ndvi(bands.nir, bands.red)
    mndwi = compute_mndwi(bands.green, bands.swir16)
    # Sum of raw reflectance across all four bands -- excludes
    # near-zero-reflectance pixels (deep water, cloud shadow) where
    # every ratio-based index above becomes numerically unstable, see
    # built_up.py's module docstring.
    brightness = bands.red + bands.green + bands.nir + bands.swir16
    mask = built_up_mask(ndbi, ndvi, mndwi, brightness, ndbi_threshold, ndvi_threshold)
    feature_collection = vectorize_mask(mask, bands.transform, bands.crs)

    if image_dir is not None:
        os.makedirs(image_dir, exist_ok=True)
        save_true_colour_png(
            bands.red, bands.green, bands.blue, os.path.join(image_dir, "true_colour.png")
        )
        save_index_heatmap_png(ndbi, os.path.join(image_dir, "ndbi.png"))
        save_index_heatmap_png(ndvi, os.path.join(image_dir, "ndvi.png"), vmin=-0.2, vmax=0.6)
        save_index_heatmap_png(mndwi, os.path.join(image_dir, "mndwi.png"))

    return BuiltUpResult(
        feature_collection=feature_collection,
        scene_id=bands.scene_id,
        scene_datetime=bands.datetime,
        cloud_cover=bands.cloud_cover,
        bounds_wgs84=bands.bounds_wgs84,
        ndbi_threshold=ndbi_threshold,
        ndvi_threshold=ndvi_threshold,
    )
