"""Coarse built-up-area detection from Sentinel-2 spectral indices.

This is NOT building-footprint detection. Sentinel-2 is 10m/pixel; a
typical house is roughly one pixel or smaller. What this module can
honestly deliver is "dense urban texture vs. vegetation/water", useful
for a rough extent/density read, not for numbering individual
buildings (that still needs Open Buildings-grade sub-metre imagery --
see discrepancies.md "Sovereign building/road detection model").

Verified 2026-09-21 against a real Sentinel-2 scene over Huambo's
actual (confirmed) centre: the combined NDBI+NDVI mask visually tracks
the city's street grid and correctly excludes its parks/watercourses,
but is over-inclusive at the city's edges (classifies bare/cleared
ground as "built-up" alongside real buildings) -- a known, published
limitation of NDBI, not something this implementation fixes. Treat
its output as a density signal to sanity-check other sources against,
not as ground truth.
"""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom


def compute_ndbi(swir16: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized Difference Built-up Index: (SWIR - NIR) / (SWIR + NIR)."""
    return (swir16 - nir) / (swir16 + nir + 1e-6)


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index: (NIR - Red) / (NIR + Red)."""
    return (nir - red) / (nir + red + 1e-6)


def built_up_mask(
    ndbi: np.ndarray,
    ndvi: np.ndarray,
    ndbi_threshold: float = 0.0,
    ndvi_threshold: float = 0.3,
) -> np.ndarray:
    """Boolean mask: NDBI above threshold AND NDVI below threshold.

    Combining both (rather than NDBI alone) excludes vegetated parks
    and watercourses inside a city, which NDBI alone misclassifies as
    built-up. It does NOT reliably exclude bare/cleared soil, which
    shares NDBI's spectral signature with built surfaces -- see the
    module docstring.
    """
    return (ndbi > ndbi_threshold) & (ndvi < ndvi_threshold)


def vectorize_mask(mask: np.ndarray, transform: rasterio.Affine, crs: str) -> dict:
    """Convert a boolean raster mask to a GeoJSON FeatureCollection (EPSG:4326)."""
    features = []
    for geom, value in shapes(mask.astype("uint8"), mask=mask, transform=transform):
        geom_wgs84 = transform_geom(crs, "EPSG:4326", geom)
        features.append(
            {
                "type": "Feature",
                "properties": {"built_up": bool(value)},
                "geometry": geom_wgs84,
            }
        )
    return {"type": "FeatureCollection", "features": features}
