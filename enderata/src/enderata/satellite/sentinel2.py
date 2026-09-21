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
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from pystac_client import Client
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

CATALOG_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Wikipedia / geodatos.net, cross-checked 2026-09-21 -- see
# discrepancies.md. Previously an unverified guess; now confirmed.
HUAMBO_CENTRE = (-12.77611, 15.73917)  # (lat, lon)


@dataclass(frozen=True)
class SceneBands:
    """A small windowed read of a few bands from one Sentinel-2 scene, all
    resampled to the same pixel grid so they can be combined directly."""

    red: np.ndarray
    nir: np.ndarray
    swir16: np.ndarray
    transform: rasterio.Affine
    crs: str
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
    """Windowed-read red/nir/swir16 for `bbox_wgs84` from a STAC item.

    `out_size` controls the output raster's side length in pixels (all
    three bands are resampled to this common grid, since swir16 ships
    at 20m native resolution vs 10m for red/nir).
    """

    def _read(asset_key: str) -> tuple[np.ndarray, rasterio.Affine, str]:
        href = item.assets[asset_key].href
        with rasterio.open(href) as ds:
            bounds_proj = transform_bounds("EPSG:4326", ds.crs, *bbox_wgs84)
            window = from_bounds(*bounds_proj, transform=ds.transform)
            arr = ds.read(1, window=window, out_shape=(out_size, out_size)).astype("float32")
            transform = ds.window_transform(window)
            crs = ds.crs.to_string()
        return arr, transform, crs

    red, transform, crs = _read("red")
    nir, _, _ = _read("nir")
    swir16, _, _ = _read("swir16")

    return SceneBands(
        red=red,
        nir=nir,
        swir16=swir16,
        transform=transform,
        crs=crs,
        scene_id=item.id,
        cloud_cover=float(item.properties.get("eo:cloud_cover", -1)),
        datetime=str(item.datetime),
    )
