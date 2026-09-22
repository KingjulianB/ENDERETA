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

from dataclasses import dataclass

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.transform import array_bounds
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

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


def read_bands(item, bbox_wgs84: tuple[float, float, float, float], out_size: int = 600) -> SceneBands:
    """Windowed-read red/green/blue/nir/swir16 for `bbox_wgs84` from a
    STAC item.

    `out_size` controls the output raster's side length in pixels (all
    bands are resampled to this common grid, since swir16 ships at 20m
    native resolution vs 10m for the others).
    """

    def _read(asset_key: str) -> tuple[np.ndarray, rasterio.Affine, str, tuple]:
        href = item.assets[asset_key].href
        with rasterio.open(href) as ds:
            bounds_proj = transform_bounds("EPSG:4326", ds.crs, *bbox_wgs84)
            window = from_bounds(*bounds_proj, transform=ds.transform)
            arr = ds.read(1, window=window, out_shape=(out_size, out_size)).astype("float32")
            transform = ds.window_transform(window)
            crs = ds.crs.to_string()
            window_bounds_proj = array_bounds(out_size, out_size, transform)
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
