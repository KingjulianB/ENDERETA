import numpy as np
from rasterio.transform import from_origin

from enderata.satellite.built_up import (
    built_up_mask,
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


def test_built_up_mask_excludes_vegetated_pixels():
    # top-left: high NDBI, low NDVI -> built-up
    # top-right: high NDBI, high NDVI (a park) -> excluded
    ndbi = np.array([[0.2, 0.2], [-0.1, -0.1]])
    ndvi = np.array([[0.1, 0.6], [0.1, 0.6]])
    mask = built_up_mask(ndbi, ndvi)
    assert mask.tolist() == [[True, False], [False, False]]


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
