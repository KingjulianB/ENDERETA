from enderata.numbering.ordering import BuildingOnStreet, assign_house_numbers


def test_assigns_alternating_numbers_per_side():
    buildings = [
        BuildingOnStreet("b1", "s1", distance_along_street=10.0, side="odd"),
        BuildingOnStreet("b2", "s1", distance_along_street=5.0, side="odd"),
        BuildingOnStreet("b3", "s1", distance_along_street=8.0, side="even"),
    ]

    numbers = {r.building_id: r.number for r in assign_house_numbers(buildings)}

    assert numbers["b2"] == 1  # nearest on the odd side
    assert numbers["b1"] == 3
    assert numbers["b3"] == 2  # only building on the even side


def test_separate_streets_number_independently():
    buildings = [
        BuildingOnStreet("b1", "s1", distance_along_street=0.0, side="odd"),
        BuildingOnStreet("b2", "s2", distance_along_street=0.0, side="odd"),
    ]

    numbers = {r.building_id: r.number for r in assign_house_numbers(buildings)}
    assert numbers["b1"] == 1
    assert numbers["b2"] == 1
