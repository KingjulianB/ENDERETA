import math

from enderata.ingestion.osm_streets import UNNAMED, _clean_name


def test_clean_name_passes_through_a_plain_string():
    assert _clean_name("Avenida Revolucao de Outubro") == "Avenida Revolucao de Outubro"


def test_clean_name_falls_back_for_nan():
    assert _clean_name(math.nan) == UNNAMED


def test_clean_name_falls_back_for_none():
    assert _clean_name(None) == UNNAMED


def test_clean_name_takes_first_element_of_a_list():
    assert _clean_name(["Rua A", "Rua B"]) == "Rua A"


def test_clean_name_falls_back_for_empty_list():
    assert _clean_name([]) == UNNAMED
