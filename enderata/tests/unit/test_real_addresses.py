import pytest
from shapely.geometry import Point

from enderata.real_addresses import run_real_addressing


def test_run_real_addressing_rejects_unknown_building_source():
    # Deliberately never reaches a network call: the source is
    # validated before load_osm_streets()/load_open_buildings_points()
    # -- an invalid value must fail fast, not after fetching data.
    with pytest.raises(ValueError, match="unknown building_source"):
        run_real_addressing(Point(13.23, -8.84).buffer(0.01), "AO", "LUA", building_source="not_a_real_source")
