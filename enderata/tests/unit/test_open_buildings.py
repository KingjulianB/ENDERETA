import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from enderata.ingestion.open_buildings import _footprints_to_points


def _square(cx: float, cy: float, half: float = 0.0001) -> Polygon:
    return Polygon(
        [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)]
    )


def test_footprints_to_points_collapses_each_footprint_to_its_centroid():
    footprints = gpd.GeoDataFrame(
        {
            "building_id": ["ob-google-0", "ob-microsoft-1"],
            "geometry": [_square(13.23, -8.84), _square(13.24, -8.85)],
            "bf_source": ["google", "microsoft"],
            "confidence": [0.9, None],
            "area_in_meters": [50.0, 60.0],
        },
        crs="EPSG:4326",
    )

    points = _footprints_to_points(footprints)

    assert list(points["building_id"]) == ["ob-google-0", "ob-microsoft-1"]
    assert all(geom.geom_type == "Point" for geom in points.geometry)
    assert points.geometry.iloc[0].x == pytest.approx(13.23)
    assert points.geometry.iloc[0].y == pytest.approx(-8.84)
    assert points.crs == footprints.crs


def test_footprints_to_points_has_no_address_or_type_data():
    footprints = gpd.GeoDataFrame(
        {
            "building_id": ["ob-google-0"],
            "geometry": [_square(13.23, -8.84)],
            "bf_source": ["google"],
            "confidence": [0.9],
            "area_in_meters": [50.0],
        },
        crs="EPSG:4326",
    )

    points = _footprints_to_points(footprints)

    assert points["building_type"].iloc[0] == "other"
    assert points["osm_street_name"].iloc[0] is None
    assert points["osm_housenumber"].iloc[0] is None
    assert points["osm_name"].iloc[0] is None


def test_footprints_to_points_preserves_row_count_and_order():
    footprints = gpd.GeoDataFrame(
        {
            "building_id": [f"ob-google-{i}" for i in range(5)],
            "geometry": [_square(13.2 + i * 0.001, -8.8) for i in range(5)],
            "bf_source": ["google"] * 5,
            "confidence": [0.5] * 5,
            "area_in_meters": [10.0] * 5,
        },
        crs="EPSG:4326",
    )

    points = _footprints_to_points(footprints)

    assert len(points) == 5
    assert list(points["building_id"]) == list(footprints["building_id"])
