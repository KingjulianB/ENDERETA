"""PNG rendering for satellite bands/indices, so a human can inspect
what the built-up mask was actually computed from -- not just the final
vectorized polygons -- and judge whether the NDBI/NDVI thresholds need
adjusting. No matplotlib dependency: plain numpy + Pillow is enough for
a percentile-stretched RGB and a simple diverging-colour heatmap.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _percentile_stretch(array: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
    """Raw Sentinel-2 L2A reflectance values aren't in a displayable 0-255
    range -- stretch between the low/high percentiles instead of the
    literal min/max, so a few very bright/dark outlier pixels don't wash
    out the rest of the image."""
    lo, hi = np.percentile(array, [low, high])
    if hi <= lo:
        hi = lo + 1.0
    stretched = np.clip((array - lo) / (hi - lo), 0, 1)
    return (stretched * 255).astype("uint8")


def save_true_colour_png(red: np.ndarray, green: np.ndarray, blue: np.ndarray, path: str) -> None:
    rgb = np.stack(
        [_percentile_stretch(red), _percentile_stretch(green), _percentile_stretch(blue)],
        axis=-1,
    )
    Image.fromarray(rgb, mode="RGB").save(path)


def save_index_heatmap_png(index: np.ndarray, path: str, vmin: float = -0.3, vmax: float = 0.3) -> None:
    """Blue (low) -> white (mid) -> red (high). Good enough to eyeball
    NDBI/NDVI without pulling in matplotlib for a colormap."""
    normalized = np.clip((index - vmin) / (vmax - vmin), 0, 1)
    red = (normalized * 255).astype("uint8")
    blue = ((1 - normalized) * 255).astype("uint8")
    green = (255 - np.abs(normalized - 0.5) * 2 * 255).astype("uint8")
    rgb = np.stack([red, green, blue], axis=-1)
    Image.fromarray(rgb, mode="RGB").save(path)
