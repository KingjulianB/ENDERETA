import geopandas as gpd
from shapely.geometry import Polygon, box

from enderata.ml.maxar_dataset import list_patch_bounds, rasterize_footprints_in_patch

CRS = "EPSG:32733"


def _square_aoi_wgs84():
    # A small square in WGS84 -- exact shape doesn't matter, just needs
    # to reproject to something with a real bounding box in CRS.
    return box(13.20, -8.90, 13.21, -8.89)


def test_list_patch_bounds_tiles_the_aoi_bbox():
    aoi = _square_aoi_wgs84()
    patches = list_patch_bounds(aoi, patch_size_px=100, resolution_m=1.0)  # 100m patches
    assert len(patches) > 0
    for west, south, east, north in patches:
        assert east - west == 100.0
        assert north - south == 100.0


def test_list_patch_bounds_only_keeps_patches_intersecting_the_real_aoi():
    # A very non-square AOI (an L-shape) in a projected CRS, reprojected
    # to WGS84 for the function's expected input -- the bbox tiling
    # must not return patches from deep inside the bbox's empty corner
    # (the L-shape's concave vertex at (500,500) means a patch touching
    # only that single boundary point still counts as "intersecting",
    # which is correct tiling behaviour -- so check a point well inside
    # the empty region instead of the corner itself).
    l_shape_proj = Polygon([(0, 0), (1000, 0), (1000, 500), (500, 500), (500, 1000), (0, 1000)])
    gdf = gpd.GeoDataFrame({"geometry": [l_shape_proj]}, crs=CRS)
    aoi_wgs84 = gdf.to_crs("EPSG:4326").geometry.iloc[0]

    patches = list_patch_bounds(aoi_wgs84, patch_size_px=100, crs=CRS, resolution_m=1.0)
    # fewer than the full 10x10 bbox tiling -- some patches were excluded
    assert len(patches) < 100
    # a patch centred deep inside the empty square (not touching its boundary)
    for west, south, east, north in patches:
        centre_x, centre_y = (west + east) / 2, (south + north) / 2
        deep_in_empty_corner = 600 < centre_x < 900 and 600 < centre_y < 900
        assert not deep_in_empty_corner


def test_rasterize_footprints_in_patch_places_building_at_the_right_pixel():
    bounds_proj = (0.0, 0.0, 100.0, 100.0)
    # 1m/pixel over a 100x100 patch -- a building near the north-west
    # corner (x close to 0, y close to 100) lands at array[0, 0].
    polygon = Polygon([(0.1, 99.1), (5.9, 99.1), (5.9, 99.9), (0.1, 99.9)])
    footprints = gpd.GeoDataFrame({"geometry": [polygon]}, crs=CRS)

    mask = rasterize_footprints_in_patch(footprints, bounds_proj, patch_size_px=100, crs=CRS)
    assert mask.shape == (100, 100)
    assert mask[0, 0] == 1
    assert mask.sum() < 100  # only the building's own few pixels, not the whole patch


def test_rasterize_footprints_in_patch_ignores_buildings_outside_the_patch():
    bounds_proj = (0.0, 0.0, 100.0, 100.0)
    far_away_polygon = Polygon([(5000, 5000), (5010, 5000), (5010, 5010), (5000, 5010)])
    footprints = gpd.GeoDataFrame({"geometry": [far_away_polygon]}, crs=CRS)

    mask = rasterize_footprints_in_patch(footprints, bounds_proj, patch_size_px=100, crs=CRS)
    assert mask.sum() == 0


def test_rasterize_footprints_in_patch_handles_empty_geodataframe():
    footprints = gpd.GeoDataFrame({"geometry": []}, crs=CRS)
    mask = rasterize_footprints_in_patch(footprints, (0.0, 0.0, 100.0, 100.0), patch_size_px=50, crs=CRS)
    assert mask.shape == (50, 50)
    assert mask.sum() == 0
