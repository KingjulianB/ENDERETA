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

**Water exclusion, added 2026-09-22** (user: "le masque confond la mer
comme une zone habitable"). Verified against a real Sentinel-2 scene
over Luanda's real coastal AOI: NDBI+NDVI alone flagged ~73% of
clearly-water (very-low-NIR) pixels as "built_up" -- two distinct real
causes, found by sampling actual pixels, not guessed:
1. A real, visible coastal lagoon (moderate reflectance, e.g.
   red=207 green=306 nir=191 swir=240) gets the classic published
   NDBI/water confusion: ndbi=0.114 (>0), ndvi=-0.040 (<0.3) --
   both pass the old thresholds. Fixed with MNDWI (Green vs SWIR,
   not NIR -- specifically designed to counter NDBI's own SWIR
   dependence, the standard remote-sensing fix for exactly this
   confusion): mndwi=0.121 (>0) correctly flags it as water.
2. Very dark, near-floor pixels (e.g. deep ocean: red=1 green=1
   nir=25 swir=124 -- all near the sensor's noise floor) make EVERY
   ratio-based index (NDBI, NDVI, and even MNDWI itself) numerically
   unstable: tiny absolute differences swing the ratio wildly (one
   such pixel had ndvi=0.923, high enough to dodge the ndvi<0.3 water
   exclusion entirely, from red=1/nir=25 alone). No spectral-index
   threshold fixes this reliably, because the underlying reflectance
   values themselves aren't trustworthy at this brightness. Fixed with
   a minimum-brightness gate (sum of red+green+nir+swir16) -- real
   built surfaces are never this dark in any of these bands at once
   (verified: real urban samples summed 6000-9000+, comfortably above
   the 300 floor; problem pixels summed 150-280).
Verified end to end after the fix on the same real scene: water
pixels wrongly flagged as built-up dropped from 58,572 to 2,276 (a
96% reduction) with no measurable loss of real urban coverage (sample
urban pixels' brightness is 20-30x the floor).
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


def compute_mndwi(green: np.ndarray, swir16: np.ndarray) -> np.ndarray:
    """Modified Normalized Difference Water Index: (Green - SWIR) / (Green + SWIR).

    Uses SWIR instead of NIR (unlike the original McFeeters NDWI) --
    the standard fix specifically for the NDBI/water confusion this
    module exists to correct, since NDBI itself is built on SWIR:
    real water strongly absorbs SWIR (unlike NIR, which some turbid/
    shallow water still reflects a fair amount of), so MNDWI separates
    water from built surfaces (which reflect more SWIR) more reliably
    than NDBI+NDVI alone. Positive -> water."""
    return (green - swir16) / (green + swir16 + 1e-6)


def built_up_mask(
    ndbi: np.ndarray,
    ndvi: np.ndarray,
    mndwi: np.ndarray,
    brightness: np.ndarray,
    ndbi_threshold: float = 0.0,
    ndvi_threshold: float = 0.3,
    mndwi_threshold: float = 0.0,
    min_brightness: float = 300.0,
) -> np.ndarray:
    """Boolean mask: NDBI above threshold AND NDVI below threshold AND
    NOT water (MNDWI at or below threshold) AND bright enough for any
    of these ratios to be numerically trustworthy in the first place.

    NDBI+NDVI alone excludes vegetated parks but NOT water bodies (see
    module docstring) -- `mndwi`/`mndwi_threshold` fixes that for real,
    moderate-reflectance water. `brightness`/`min_brightness` (sum of
    red+green+nir+swir16, all in the same raw reflectance units)
    additionally excludes near-zero-reflectance pixels (very dark
    ocean, cloud shadow, sensor edge artifacts) where EVERY index here
    -- MNDWI included -- becomes numerically unstable and can't be
    trusted either way; no combination of index thresholds fixes that,
    only refusing to classify pixels that dark at all does. Does NOT
    reliably exclude bare/cleared soil, which shares NDBI's spectral
    signature with built surfaces -- see the module docstring.
    """
    return (
        (ndbi > ndbi_threshold)
        & (ndvi < ndvi_threshold)
        & (mndwi <= mndwi_threshold)
        & (brightness > min_brightness)
    )


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
