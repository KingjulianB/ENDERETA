from shapely.geometry import LineString, Point

from enderata.numbering.street_assignment import Street, StreetIndex, assign_building_to_street


def test_assigns_building_to_nearest_street():
    street_a = Street("s1", "Rua A", LineString([(0, 0), (10, 0)]))
    street_b = Street("s2", "Rua B", LineString([(0, 5), (10, 5)]))
    index = StreetIndex([street_a, street_b])

    result = assign_building_to_street(Point(3, 0.2), index)

    assert result is not None
    assert result.street_id == "s1"
    assert result.distance_along_street == 3.0


def test_opposite_sides_get_different_labels():
    street = Street("s1", "Rua A", LineString([(0, 0), (10, 0)]))
    index = StreetIndex([street])

    north = assign_building_to_street(Point(3, 1), index)
    south = assign_building_to_street(Point(3, -1), index)

    assert north.side != south.side


def test_max_distance_filters_out_far_buildings():
    street = Street("s1", "Rua A", LineString([(0, 0), (10, 0)]))
    index = StreetIndex([street])
    result = assign_building_to_street(Point(3, 100), index, max_distance=5)
    assert result is None


def test_empty_street_index_returns_none():
    index = StreetIndex([])
    result = assign_building_to_street(Point(3, 0.2), index)
    assert result is None
