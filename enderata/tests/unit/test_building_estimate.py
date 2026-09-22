from enderata.satellite.building_estimate import estimate_building_points


def _square_feature_collection(west, south, east, north):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"built_up": True},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [west, south],
                            [east, south],
                            [east, north],
                            [west, north],
                            [west, south],
                        ]
                    ],
                },
            }
        ],
    }


def test_estimate_building_points_stay_inside_the_built_up_polygon():
    # ~0.01 degrees on a side at the equator is roughly 1.1km -- big
    # enough for several grid points at spacing_m=200.
    fc = _square_feature_collection(0.0, 0.0, 0.01, 0.01)
    points = estimate_building_points(fc, spacing_m=200.0)

    assert len(points) > 0
    assert list(points.columns) == ["building_id", "geometry"]
    assert str(points.crs) == "EPSG:4326"
    assert all(0.0 <= geom.x <= 0.01 and 0.0 <= geom.y <= 0.01 for geom in points.geometry)


def test_estimate_building_points_ignores_non_built_up_features():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"built_up": False},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }
    points = estimate_building_points(fc)
    assert len(points) == 0
    assert list(points.columns) == ["building_id", "geometry"]


def test_estimate_building_points_empty_feature_collection():
    fc = {"type": "FeatureCollection", "features": []}
    points = estimate_building_points(fc)
    assert len(points) == 0


def test_estimate_building_points_respects_max_points_cap():
    # Dense grid (small spacing over a moderately large square) would
    # produce far more than max_points -- the cap must still hold.
    fc = _square_feature_collection(0.0, 0.0, 0.05, 0.05)
    points = estimate_building_points(fc, spacing_m=50.0, max_points=25)
    assert 0 < len(points) <= 25


def test_estimate_building_points_ids_are_unique_and_sequential():
    fc = _square_feature_collection(0.0, 0.0, 0.01, 0.01)
    points = estimate_building_points(fc, spacing_m=200.0)
    ids = points["building_id"].tolist()
    assert ids == [f"est-{i:05d}" for i in range(len(ids))]
    assert len(set(ids)) == len(ids)
