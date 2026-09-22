"""Build a real, supervised patch dataset for BUILDING FOOTPRINT
SEGMENTATION (not just per-pixel built-up classification) using the
real 0.5m/pixel Maxar 2017 Luanda mosaic + real OSM building polygons
as labels.

LICENSE (read before using this module for anything beyond local
prototyping): the Maxar mosaic is CC BY-NC 4.0 (Maxar's Open Data
Program is systematically non-commercial -- verified against the raw
OpenAerialMap API and Maxar's own program docs, see discrepancies.md
"Own neural network for built-up detection"). It was mistakenly
recorded as CC-BY 4.0 earlier in this project's history; that was
wrong. User's explicit decision (2026-09-22): current work is
non-commercial prototyping, permitted under this license; any model
trained on this data must be RE-TRAINED on properly licensed imagery
before commercial/government use -- the weights themselves are a
likely derivative of NC-licensed data, not just "unlockable" with a
later paid license.

At 0.5m/pixel, individual buildings are many pixels across -- unlike
ml/dataset.py's Sentinel-2-based per-pixel classifier, this dataset
supports real per-building footprint segmentation (SpaceNet-style),
the original scope the user asked for before the licensing issue was
found.

The full mosaic covers ~131072x114688 pixels (~15 billion pixels) --
far too large to materialize at once. This module tiles the real
Luanda AOI into fixed-size patches and fetches/rasterizes them one at
a time via windowed HTTP reads (the file is a real Cloud-Optimized
GeoTIFF on S3 -- verified: opens in ~1.5s, a 200x200px windowed read
in ~0.6s), keeping only patches that actually intersect the AOI
polygon (most of a bbox around Luanda's coastline is ocean).
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.windows import from_bounds as window_from_bounds
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from enderata.ingestion.osm_buildings import load_osm_building_footprints

MAXAR_LUANDA_URL = "https://oin-hotosm-temp.s3.amazonaws.com/5eabb9753295f300072a6d5a/0/5eabb9753295f300072a6d5b.tif"
MAXAR_LUANDA_CRS = "EPSG:32733"  # UTM zone 33S -- the mosaic's own native CRS
MAXAR_LUANDA_LICENSE = "CC BY-NC 4.0 (Maxar Open Data Program) -- non-commercial use only, see module docstring"
MAXAR_RESOLUTION_M = 0.5


@dataclass(frozen=True)
class Patch:
    rgb: np.ndarray  # (3, patch_size_px, patch_size_px) uint8
    label_mask: np.ndarray  # (patch_size_px, patch_size_px) uint8: 1 = real building footprint
    bounds_proj: tuple[float, float, float, float]  # (west, south, east, north) in MAXAR_LUANDA_CRS


def _tile_bounds(minx: float, miny: float, maxx: float, maxy: float, patch_size_m: float):
    y = miny
    while y < maxy:
        x = minx
        while x < maxx:
            yield (x, y, x + patch_size_m, y + patch_size_m)
            x += patch_size_m
        y += patch_size_m


def list_patch_bounds(
    aoi: BaseGeometry,
    patch_size_px: int = 512,
    crs: str = MAXAR_LUANDA_CRS,
    resolution_m: float = MAXAR_RESOLUTION_M,
) -> list[tuple[float, float, float, float]]:
    """Tile `aoi`'s bounding box (reprojected to `crs`) into
    `patch_size_px` x `patch_size_px` squares at `resolution_m`/pixel,
    keeping only ones that actually intersect the real AOI polygon.
    Pure geometry -- no network call (`to_crs` uses local PROJ data)."""
    aoi_proj = gpd.GeoSeries([aoi], crs="EPSG:4326").to_crs(crs).iloc[0]
    minx, miny, maxx, maxy = aoi_proj.bounds
    patch_size_m = patch_size_px * resolution_m

    return [
        bounds
        for bounds in _tile_bounds(minx, miny, maxx, maxy, patch_size_m)
        if aoi_proj.intersects(box(*bounds))
    ]


def rasterize_footprints_in_patch(
    footprints_gdf: gpd.GeoDataFrame,
    bounds_proj: tuple[float, float, float, float],
    patch_size_px: int,
    crs: str = MAXAR_LUANDA_CRS,
) -> np.ndarray:
    """Binary mask for one patch: 1 where a real OSM building footprint
    (already reprojected to `crs`, see build_patch_dataset) overlaps
    that pixel. `footprints_gdf` must already be in `crs` -- reprojecting
    per patch instead of once for the whole dataset would be wasteful."""
    west, south, east, north = bounds_proj
    candidates = footprints_gdf[footprints_gdf.geometry.intersects(box(*bounds_proj))]
    if len(candidates) == 0:
        return np.zeros((patch_size_px, patch_size_px), dtype="uint8")

    transform = transform_from_bounds(west, south, east, north, patch_size_px, patch_size_px)
    shapes = [
        (geom.buffer(1.0) if geom.geom_type == "Point" else geom, 1)
        for geom in candidates.geometry
        if geom is not None and not geom.is_empty
    ]
    return rasterize(shapes, out_shape=(patch_size_px, patch_size_px), transform=transform, fill=0, dtype="uint8")


def build_patch_dataset(
    aoi: BaseGeometry,
    patch_size_px: int = 512,
    max_patches: int | None = 300,
    maxar_url: str = MAXAR_LUANDA_URL,
    footprints_gdf: gpd.GeoDataFrame | None = None,
) -> list[Patch]:
    """Fetch real Maxar 0.5m imagery + rasterize real building
    footprints for a tiled set of patches covering `aoi`. Opens the
    remote COG once and reuses the handle across all patches (each
    windowed read is cheap; repeatedly reopening the dataset per patch
    is not). `max_patches` caps how many patches are fetched (None =
    all patches intersecting the AOI, which can be several thousand
    for the full Luanda municipality -- cap for a manageable
    prototyping run).

    `footprints_gdf` overrides the default OSM footprint source (see
    `ingestion/osm_buildings.py`) with a pre-loaded GeoDataFrame in
    EPSG:4326 -- e.g. `ingestion/open_buildings.py`'s Google/Microsoft/
    OSM combined dataset, used because OSM's own building coverage in
    Luanda turned out too sparse to train a building-segmentation model
    against (verified 2026-09-22, see discrepancies.md)."""
    patch_bounds_list = list_patch_bounds(aoi, patch_size_px=patch_size_px)
    if max_patches is not None:
        patch_bounds_list = patch_bounds_list[:max_patches]

    source = footprints_gdf if footprints_gdf is not None else load_osm_building_footprints(aoi)
    footprints = source.to_crs(MAXAR_LUANDA_CRS)

    patches: list[Patch] = []
    with rasterio.open(maxar_url) as ds:
        for bounds_proj in patch_bounds_list:
            window = window_from_bounds(*bounds_proj, transform=ds.transform)
            rgb = ds.read([1, 2, 3], window=window, out_shape=(patch_size_px, patch_size_px))
            label_mask = rasterize_footprints_in_patch(footprints, bounds_proj, patch_size_px)
            patches.append(Patch(rgb=rgb, label_mask=label_mask, bounds_proj=bounds_proj))

    return patches


def save_patch_dataset(patches: list[Patch], path: str) -> None:
    """Writes `<path>.npz`: stacked rgb/label_mask arrays plus their
    per-patch bounds, so patches stay addressable after reload."""
    np.savez_compressed(
        f"{path}.npz",
        rgb=np.stack([p.rgb for p in patches]),
        label_mask=np.stack([p.label_mask for p in patches]),
        bounds_proj=np.array([p.bounds_proj for p in patches]),
    )


def load_patch_dataset(path: str) -> list[Patch]:
    arrays = np.load(f"{path}.npz")
    return [
        Patch(rgb=rgb, label_mask=label_mask, bounds_proj=tuple(bounds))
        for rgb, label_mask, bounds in zip(arrays["rgb"], arrays["label_mask"], arrays["bounds_proj"])
    ]
