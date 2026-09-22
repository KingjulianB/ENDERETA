"""Build a real, supervised training dataset for a built-up-area
segmentation model: Sentinel-2 multispectral bands (input) + a binary
mask rasterized from real OSM building footprints (label), aligned to
the same pixel grid.

IMPORTANT scope limit (see discrepancies.md, 2026-09-22 "own neural
network" decision): Sentinel-2 is 10m/pixel and a typical building is
smaller than one pixel. This dataset cannot train a per-building
INSTANCE segmentation model (SpaceNet-style building outlines) -- what
it can train is a per-pixel "does real building footprint overlap this
10m cell" predictor, i.e. a LEARNED replacement for the hand-tuned
NDBI/NDVI threshold rule in satellite/built_up.py, not a building
detector. No sub-metre commercially-licensed imagery exists for Luanda
(checked: Planet NICFI, OSM editor imagery, and Maxar's Open Data
Program -- including the specific Luanda mosaic previously thought to
be CC-BY -- are all non-commercial-only; see discrepancies.md), so this
resolution ceiling is a real constraint, not a shortcut.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry.base import BaseGeometry

from enderata.ingestion.osm_buildings import load_osm_building_footprints
from enderata.satellite.sentinel2 import find_recent_scene, read_bands

# Buffer radius (metres) for single-node buildings (bare Point geometry,
# ~1.5% of Luanda's real OSM buildings, see osm_buildings.py) --
# rasterize can't fill a zero-area point, so give it a small real-world
# footprint instead of dropping it from the training labels entirely.
POINT_BUFFER_M = 3.0

BAND_NAMES = ("red", "green", "blue", "nir", "swir16")


@dataclass(frozen=True)
class TrainingDataset:
    bands: np.ndarray  # (5, H, W) float32, order = BAND_NAMES
    label_mask: np.ndarray  # (H, W) uint8: 1 = a real OSM building footprint overlaps this pixel
    transform: rasterio.Affine
    crs: str
    bounds_wgs84: tuple[float, float, float, float]
    scene_id: str
    scene_datetime: str


def rasterize_building_mask(
    buildings_gdf: gpd.GeoDataFrame,
    transform: rasterio.Affine,
    crs: str,
    shape: tuple[int, int],
) -> np.ndarray:
    """Binary mask, 1 where a real OSM building footprint overlaps
    that pixel. `buildings_gdf` is reprojected to `crs` (must match
    `transform`'s CRS) before rasterizing; Point geometries are
    buffered by `POINT_BUFFER_M` metres first."""
    if len(buildings_gdf) == 0:
        return np.zeros(shape, dtype="uint8")

    projected = buildings_gdf.to_crs(crs)
    shapes = [
        (geom.buffer(POINT_BUFFER_M) if geom.geom_type == "Point" else geom, 1)
        for geom in projected.geometry
        if geom is not None and not geom.is_empty
    ]
    if not shapes:
        return np.zeros(shape, dtype="uint8")

    return rasterize(shapes, out_shape=shape, transform=transform, fill=0, dtype="uint8")


def build_training_dataset(
    aoi: BaseGeometry, max_cloud_cover: float = 20.0, max_dimension: int = 2000
) -> TrainingDataset:
    """Fetch a real Sentinel-2 scene over `aoi` and real OSM building
    footprints within it, and rasterize the footprints onto the
    scene's own pixel grid -- input/label pair for supervised
    training. Raises RuntimeError if no scene is found (see
    sentinel2.find_recent_scene)."""
    bbox_wgs84 = aoi.bounds
    item = find_recent_scene(bbox_wgs84, max_cloud_cover=max_cloud_cover)
    scene = read_bands(item, bbox_wgs84, max_dimension=max_dimension)

    bands = np.stack([scene.red, scene.green, scene.blue, scene.nir, scene.swir16], axis=0)

    footprints = load_osm_building_footprints(aoi)
    label_mask = rasterize_building_mask(footprints, scene.transform, scene.crs, scene.red.shape)

    return TrainingDataset(
        bands=bands,
        label_mask=label_mask,
        transform=scene.transform,
        crs=scene.crs,
        bounds_wgs84=scene.bounds_wgs84,
        scene_id=scene.scene_id,
        scene_datetime=scene.datetime,
    )


def save_training_dataset(dataset: TrainingDataset, path: str) -> None:
    """Writes `<path>.npz` (bands + label_mask arrays) and
    `<path>.json` (transform/crs/bounds/scene metadata) -- fetching a
    full-Luanda scene + rasterizing labels takes real network time, not
    worth repeating on every training run."""
    np.savez_compressed(f"{path}.npz", bands=dataset.bands, label_mask=dataset.label_mask)
    meta = {
        "transform": list(dataset.transform)[:6],
        "crs": dataset.crs,
        "bounds_wgs84": list(dataset.bounds_wgs84),
        "scene_id": dataset.scene_id,
        "scene_datetime": dataset.scene_datetime,
    }
    with open(f"{path}.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)


def load_training_dataset(path: str) -> TrainingDataset:
    arrays = np.load(f"{path}.npz")
    with open(f"{path}.json", encoding="utf-8") as f:
        meta = json.load(f)
    return TrainingDataset(
        bands=arrays["bands"],
        label_mask=arrays["label_mask"],
        transform=rasterio.Affine(*meta["transform"]),
        crs=meta["crs"],
        bounds_wgs84=tuple(meta["bounds_wgs84"]),
        scene_id=meta["scene_id"],
        scene_datetime=meta["scene_datetime"],
    )
