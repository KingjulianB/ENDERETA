import math

from enderata.ingestion.osm_buildings import _clean_str, classify_building_type


def test_classify_house_tags():
    for tag in ("house", "detached", "semidetached_house", "terrace", "bungalow", "cabin"):
        assert classify_building_type(tag) == "house"


def test_classify_apartment_tags():
    for tag in ("apartments", "dormitory"):
        assert classify_building_type(tag) == "apartment"


def test_classify_warehouse_tags():
    # No building in Luanda's real OSM data is literally tagged
    # "warehouse" (verified 2026-09-22) -- "industrial" is the closest
    # real proxy, see the module docstring.
    for tag in ("warehouse", "industrial", "storage_tank", "hangar", "factory"):
        assert classify_building_type(tag) == "warehouse"


def test_classify_is_case_insensitive():
    assert classify_building_type("House") == "house"
    assert classify_building_type("APARTMENTS") == "apartment"


def test_classify_falls_back_to_other_for_generic_and_ambiguous_tags():
    for tag in ("yes", "school", "hospital", "commercial", "office", "residential"):
        assert classify_building_type(tag) == "other"


def test_classify_falls_back_to_other_for_missing_tag():
    assert classify_building_type(None) == "other"
    assert classify_building_type(math.nan) == "other"


def test_clean_str_passes_through_a_plain_string():
    assert _clean_str("Rua A") == "Rua A"


def test_clean_str_returns_none_for_nan_and_none():
    assert _clean_str(math.nan) is None
    assert _clean_str(None) is None


def test_clean_str_takes_first_element_of_a_list():
    assert _clean_str(["Rua A", "Rua B"]) == "Rua A"


def test_clean_str_returns_none_for_empty_list():
    assert _clean_str([]) is None
