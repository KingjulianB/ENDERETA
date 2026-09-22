import geopandas as gpd
import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import Point, Polygon

from enderata.ml.dataset import rasterize_building_mask

# A simple 10x10 grid, 10m pixels, origin at (0, 100) in a metric CRS --
# pixel (row, col) covers [col*10, (col+1)*10) x (100-(row+1)*10, 100-row*10)
TRANSFORM = from_origin(0, 100, 10, 10)
CRS = "EPSG:32733"  # UTM zone 33S, same as the real Sentinel-2 scenes used
SHAPE = (10, 10)


def test_empty_geodataframe_returns_all_zero_mask():
    buildings = gpd.GeoDataFrame({"geometry": []}, crs=CRS)
    mask = rasterize_building_mask(buildings, TRANSFORM, CRS, SHAPE)
    assert mask.shape == SHAPE
    assert mask.dtype == np.uint8
    assert mask.sum() == 0


def test_polygon_footprint_is_rasterized_at_the_right_pixel():
    # A building polygon squarely inside pixel (row=0, col=0): x in
    # [0,10), y in [90,100)
    polygon = Polygon([(2, 92), (8, 92), (8, 98), (2, 98)])
    buildings = gpd.GeoDataFrame({"geometry": [polygon]}, crs=CRS)
    mask = rasterize_building_mask(buildings, TRANSFORM, CRS, SHAPE)

    assert mask[0, 0] == 1
    assert mask.sum() == 1  # nothing else touched


def test_point_geometry_is_buffered_before_rasterizing():
    # A single-node building (bare Point) at the centre of pixel (0,0)
    point = Point(5, 95)
    buildings = gpd.GeoDataFrame({"geometry": [point]}, crs=CRS)
    mask = rasterize_building_mask(buildings, TRANSFORM, CRS, SHAPE)

    # An unbuffered point has zero area and would rasterize to nothing --
    # the buffer must produce at least the one pixel it sits in.
    assert mask[0, 0] == 1


def test_reprojects_to_the_target_crs_before_rasterizing():
    # Same polygon as above, but supplied in WGS84 -- must still land
    # in pixel (0,0) after reprojection to CRS.
    polygon_utm = Polygon([(2, 92), (8, 92), (8, 98), (2, 98)])
    gdf_utm = gpd.GeoDataFrame({"geometry": [polygon_utm]}, crs=CRS)
    gdf_wgs84 = gdf_utm.to_crs("EPSG:4326")

    mask = rasterize_building_mask(gdf_wgs84, TRANSFORM, CRS, SHAPE)
    assert mask[0, 0] == 1


def test_multiple_buildings_in_different_pixels():
    polygons = [
        Polygon([(2, 92), (8, 92), (8, 98), (2, 98)]),  # pixel (0,0)
        Polygon([(92, 2), (98, 2), (98, 8), (92, 8)]),  # pixel (9,9)
    ]
    buildings = gpd.GeoDataFrame({"geometry": polygons}, crs=CRS)
    mask = rasterize_building_mask(buildings, TRANSFORM, CRS, SHAPE)

    assert mask[0, 0] == 1
    assert mask[9, 9] == 1
    assert mask.sum() == 2
