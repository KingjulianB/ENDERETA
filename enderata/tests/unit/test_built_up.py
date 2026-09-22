import numpy as np
from rasterio.transform import from_origin

from enderata.satellite.built_up import (
    built_up_mask,
    compute_mndwi,
    compute_ndbi,
    compute_ndvi,
    vectorize_mask,
)


def test_compute_ndbi_matches_known_formula():
    swir = np.array([[200.0, 100.0]])
    nir = np.array([[100.0, 200.0]])
    ndbi = compute_ndbi(swir, nir)
    # (200-100)/(200+100) = 1/3 ; (100-200)/(100+200) = -1/3
    assert np.allclose(ndbi, [[1 / 3, -1 / 3]], atol=1e-4)


def test_compute_ndvi_matches_known_formula():
    nir = np.array([[300.0, 100.0]])
    red = np.array([[100.0, 300.0]])
    ndvi = compute_ndvi(nir, red)
    assert np.allclose(ndvi, [[0.5, -0.5]], atol=1e-4)


def test_compute_mndwi_matches_known_formula():
    green = np.array([[300.0, 100.0]])
    swir = np.array([[100.0, 300.0]])
    mndwi = compute_mndwi(green, swir)
    # (300-100)/(300+100) = 0.5 ; (100-300)/(100+300) = -0.5
    assert np.allclose(mndwi, [[0.5, -0.5]], atol=1e-4)


def test_built_up_mask_excludes_vegetated_pixels():
    # top-left: high NDBI, low NDVI, dry land, bright -> built-up
    # top-right: high NDBI, high NDVI (a park), bright -> excluded
    ndbi = np.array([[0.2, 0.2], [-0.1, -0.1]])
    ndvi = np.array([[0.1, 0.6], [0.1, 0.6]])
    mndwi = np.full((2, 2), -0.5)  # not water anywhere in this scenario
    brightness = np.full((2, 2), 5000.0)  # comfortably bright everywhere
    mask = built_up_mask(ndbi, ndvi, mndwi, brightness)
    assert mask.tolist() == [[True, False], [False, False]]


def test_built_up_mask_excludes_water_even_when_ndbi_and_ndvi_look_built_up():
    # Real bug (2026-09-22): a coastal lagoon passed the old NDBI+NDVI
    # check (ndbi=0.114>0, ndvi=-0.040<0.3, both "built-up"-looking)
    # despite being real water -- MNDWI must exclude it regardless.
    ndbi = np.array([[0.114]])
    ndvi = np.array([[-0.040]])
    mndwi = np.array([[0.121]])  # positive -> water
    brightness = np.array([[944.0]])  # plenty bright, not the dark-pixel case
    mask = built_up_mask(ndbi, ndvi, mndwi, brightness)
    assert mask.tolist() == [[False]]


def test_built_up_mask_excludes_near_zero_reflectance_pixels_regardless_of_indices():
    # Real bug (2026-09-22): deep-ocean pixels near the sensor's noise
    # floor (red=1 green=1 nir=25 swir=124) produced a numerically
    # unstable ndvi=0.923 -- high enough to dodge the ndvi<0.3 water
    # exclusion AND a negative mndwi (also numerically unstable at this
    # brightness). Only a minimum-brightness floor catches this.
    ndbi = np.array([[0.664]])
    ndvi = np.array([[0.923]])  # would normally fail ndvi<0.3 -- deliberately made to pass it below
    mndwi = np.array([[-0.5]])  # would normally look like "not water"
    brightness = np.array([[151.0]])  # sum of red+green+nir+swir16 -- far below the default floor
    mask = built_up_mask(ndbi, ndvi, mndwi, brightness, ndvi_threshold=1.0)
    assert mask.tolist() == [[False]]


def test_vectorize_mask_produces_valid_geojson_over_the_masked_region():
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True
    transform = from_origin(15.0, -12.0, 0.001, 0.001)  # arbitrary small pixel size

    fc = vectorize_mask(mask, transform, "EPSG:4326")

    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) >= 1
    assert all(f["properties"]["built_up"] is True for f in fc["features"])
    for feature in fc["features"]:
        assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")
