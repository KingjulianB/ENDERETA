"""Run the trained Maxar building-segmentation U-Net over a real AOI
and return detected building footprints as a GeoJSON FeatureCollection.

LOCAL/OPTIONAL feature, not part of the add-on's shipped Docker image:
requires `pip install -r requirements-ml.txt` (torch) and a checkpoint
trained locally (see ml/train_maxar.py and discrepancies.md's "Own
neural network for built-up detection" -- the Open-Buildings-labeled
run, best_val_iou=0.6098, is the one worth using). Both the checkpoint
and torch are intentionally absent from `requirements.txt`/the Docker
build -- `cli.py`'s command for this imports torch/this module lazily
so the rest of the CLI keeps working without either installed.

The checkpoint itself is a derivative of Maxar's CC BY-NC 4.0 Open
Data Program imagery: fine for this local/prototyping CLI command, NOT
for the distributed commercial product until retrained on properly
licensed imagery (MAXAR_LUANDA_LICENSE in ml/maxar_dataset.py).
"""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds as window_from_bounds
from shapely.geometry.base import BaseGeometry

from enderata.ml.maxar_dataset import MAXAR_LUANDA_CRS, MAXAR_LUANDA_URL, list_patch_bounds


def _vectorize_building_mask(mask: np.ndarray, transform: rasterio.Affine, crs: str) -> list[dict]:
    """Like `satellite/built_up.py`'s vectorize_mask, but with a
    `building` property (that module's `built_up` key doesn't fit
    per-building detections) -- kept separate rather than reused with
    a misleading property name."""
    features = []
    for geom, value in shapes(mask.astype("uint8"), mask=mask, transform=transform):
        geom_wgs84 = transform_geom(crs, "EPSG:4326", geom)
        features.append({"type": "Feature", "properties": {"building": bool(value)}, "geometry": geom_wgs84})
    return features


def detect_buildings_ml(
    aoi: BaseGeometry,
    checkpoint_path: str,
    patch_size_px: int = 512,
    max_patches: int | None = None,
    threshold: float = 0.5,
    maxar_url: str = MAXAR_LUANDA_URL,
) -> dict:
    """Real per-building segmentation via the trained U-Net -- see
    module docstring for the license/scope caveat. Tiles `aoi` the
    same way `ml/maxar_dataset.py::build_patch_dataset` does for
    training, runs inference per patch, and merges each patch's
    vectorized detections into one GeoJSON FeatureCollection
    (EPSG:4326). `max_patches` caps how many tiles are processed (None
    = the whole AOI, which can be several thousand for full Luanda --
    slow on CPU, useful to cap for a quick check)."""
    import torch

    from enderata.ml.model import UNet

    model = UNet(in_channels=3, out_channels=1, base_channels=32)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    model.to(device)
    model.eval()

    patch_bounds_list = list_patch_bounds(aoi, patch_size_px=patch_size_px, crs=MAXAR_LUANDA_CRS)
    if max_patches is not None:
        patch_bounds_list = patch_bounds_list[:max_patches]

    all_features: list[dict] = []
    with rasterio.open(maxar_url) as ds, torch.no_grad():
        for bounds_proj in patch_bounds_list:
            window = window_from_bounds(*bounds_proj, transform=ds.transform)
            rgb = ds.read([1, 2, 3], window=window, out_shape=(patch_size_px, patch_size_px))
            x = torch.from_numpy(rgb.astype("float32") / 255.0).unsqueeze(0).to(device)
            logits = model(x)
            mask = (torch.sigmoid(logits) > threshold).cpu().numpy()[0, 0].astype(bool)
            if not mask.any():
                continue
            west, south, east, north = bounds_proj
            transform = transform_from_bounds(west, south, east, north, patch_size_px, patch_size_px)
            all_features.extend(_vectorize_building_mask(mask, transform, MAXAR_LUANDA_CRS))

    return {"type": "FeatureCollection", "features": all_features}
