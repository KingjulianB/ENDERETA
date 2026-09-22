"""Fetch Sentinel-2 L2A bands from the public AWS-hosted Earth Search
catalog (Copernicus data, free for any use including commercial --
verified via ESA's Copernicus data policy, unlike Planet NICFI which is
non-commercial-only and was ruled out for that reason).

No API key or account needed: the "sentinel-2-l2a" collection on
https://earth-search.aws.element84.com/v1 is public, and its Cloud-
Optimized GeoTIFF assets support windowed HTTP reads (only the
requested area is downloaded, not the whole ~100x100km scene).

Verified working end to end against a real, current scene over Huambo
(2026-09-20, S2C_33LWF tile) -- see discrepancies.md for the coordinate
bug this caught (Huambo's real centre sits in tile 33LWF, not the
33LWG tile an unverified nearby-tile search first returned).

Pilot district changed from Huambo to Luanda 2026-09-22: real, open
(CC-BY 4.0) high-resolution imagery exists for Luanda via
OpenAerialMap (a 2017 Maxar mosaic, 0.5m/pixel) -- none exists for
Huambo at any usable resolution/licence, see discrepancies.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import transform_bounds
from rasterio.windows import bounds as window_bounds
from rasterio.windows import from_bounds as window_from_bounds

CATALOG_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Wikipedia, verified 2026-09-22 and cross-checked against a real
# Sentinel-2 true-colour scene (dense urban core, airport visible).
LUANDA_CENTRE = (-8.83833, 13.23444)  # (lat, lon)


@dataclass(frozen=True)
class SceneBands:
    """A small windowed read of a few bands from one Sentinel-2 scene, all
    resampled to the same pixel grid so they can be combined directly."""

    red: np.ndarray
    green: np.ndarray
    blue: np.ndarray
    nir: np.ndarray
    swir16: np.ndarray
    transform: rasterio.Affine
    crs: str
    bounds_wgs84: tuple[float, float, float, float]  # (west, south, east, north)
    scene_id: str
    cloud_cover: float
    datetime: str


def find_recent_scene(bbox_wgs84: tuple[float, float, float, float], max_cloud_cover: float = 20.0):
    """Return the most recent, low-cloud STAC item covering `bbox_wgs84`."""
    catalog = Client.open(CATALOG_URL)
    search = catalog.search(
        collections=[COLLECTION],
        bbox=bbox_wgs84,
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        max_items=1,
        sortby=[{"field": "properties.datetime", "direction": "desc"}],
    )
    items = list(search.items())
    if not items:
        raise RuntimeError(
            f"No Sentinel-2 scene found for bbox {bbox_wgs84} under {max_cloud_cover}% cloud cover"
        )
    return items[0]


def _compute_out_shape(
    bbox_wgs84: tuple[float, float, float, float], target_resolution_m: float = 10.0, max_dimension: int = 2000
) -> tuple[int, int]:
    """(height_px, width_px) matching `bbox_wgs84`'s real aspect ratio
    at roughly `target_resolution_m` (Sentinel-2's own native
    resolution, 10m), capped so neither side exceeds `max_dimension`
    (scaling both sides down together, so the aspect ratio -- and
    therefore the mask's real-world shape -- is preserved even when
    capped). Until 2026-09-22 this was a single fixed `out_size=600`
    forcing every bbox into a square raster regardless of its real
    shape -- fine near Huambo/Luanda's small original 1.6km-radius test
    AOI (roughly square), badly wrong for the real Luanda municipality
    boundary (~15km x 18km, see aoi.py) -- see module docstring.
    """
    west, south, east, north = bbox_wgs84
    centre_lat = (south + north) / 2
    width_m = (east - west) * 111_320 * max(math.cos(math.radians(centre_lat)), 0.01)
    height_m = (north - south) * 111_320

    width_px = max(1, round(width_m / target_resolution_m))
    height_px = max(1, round(height_m / target_resolution_m))

    longer_side = max(width_px, height_px)
    if longer_side > max_dimension:
        scale = max_dimension / longer_side
        width_px = max(1, round(width_px * scale))
        height_px = max(1, round(height_px * scale))
    return height_px, width_px


def read_bands(
    item,
    bbox_wgs84: tuple[float, float, float, float],
    out_shape: tuple[int, int] | None = None,
    max_dimension: int = 2000,
) -> SceneBands:
    """Windowed-read red/green/blue/nir/swir16 for `bbox_wgs84` from a
    STAC item.

    `out_shape` is (height_px, width_px); all bands are resampled to
    this common grid (swir16 ships at 20m native resolution vs 10m for
    the others). Defaults to `_compute_out_shape(bbox_wgs84, max_dimension=max_dimension)`
    -- sized to the bbox's real aspect ratio at ~10m/pixel, not forced
    square; `max_dimension` caps memory/processing for a large AOI
    (ignored if `out_shape` is given explicitly).
    """
    if out_shape is None:
        out_shape = _compute_out_shape(bbox_wgs84, max_dimension=max_dimension)
    height_px, width_px = out_shape

    def _read(asset_key: str) -> tuple[np.ndarray, rasterio.Affine, str, tuple]:
        href = item.assets[asset_key].href
        with rasterio.open(href) as ds:
            bounds_proj = transform_bounds("EPSG:4326", ds.crs, *bbox_wgs84)
            window = window_from_bounds(*bounds_proj, transform=ds.transform)
            arr = ds.read(1, window=window, out_shape=(height_px, width_px)).astype("float32")
            # The window's real-world bounds don't depend on out_shape --
            # computing them straight from the window (not from a
            # native-resolution transform combined with the resampled
            # array's pixel count, the previous approach) is what
            # actually fixes the bounds-mismatch bug described above.
            window_bounds_proj = window_bounds(window, ds.transform)
            transform = transform_from_bounds(*window_bounds_proj, width_px, height_px)
            crs = ds.crs.to_string()
        return arr, transform, crs, window_bounds_proj

    red, transform, crs, window_bounds_proj = _read("red")
    green, _, _, _ = _read("green")
    blue, _, _, _ = _read("blue")
    nir, _, _, _ = _read("nir")
    swir16, _, _, _ = _read("swir16")

    bounds_wgs84 = transform_bounds(crs, "EPSG:4326", *window_bounds_proj)

    return SceneBands(
        red=red,
        green=green,
        blue=blue,
        nir=nir,
        swir16=swir16,
        transform=transform,
        crs=crs,
        bounds_wgs84=bounds_wgs84,
        scene_id=item.id,
        cloud_cover=float(item.properties.get("eo:cloud_cover", -1)),
        datetime=str(item.datetime),
    )
