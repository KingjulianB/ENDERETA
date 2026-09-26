import os
from pathlib import Path

os.environ.setdefault(
    "ENDERATA_MBTILES_PATH",
    str(Path(__file__).parent.parent.parent / "tiles" / "angola.mbtiles"),
)

from enderata.tileserver import get_metadata, get_tile  # noqa: E402


def test_get_metadata_reports_the_real_nationwide_bounds():
    meta = get_metadata()
    assert meta["minzoom"] == "0"
    assert meta["maxzoom"] == "14"
    # Whole-Angola bounds (2026-09-26), not just the old Luanda-only AOI --
    # covers Cabinda's exclave in the north to the southern border.
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in meta["bounds"].split(","))
    assert 10.0 < min_lon < 12.0
    assert 23.0 < max_lon < 25.0
    assert -19.0 < min_lat < -17.0
    assert -5.0 < max_lat < -3.0


def test_get_tile_returns_bytes_for_a_known_real_tile():
    # z14/x8794/y8595 independently verified (see tileserver.py) to
    # cover Luanda's actual centre coordinate -- still valid in the
    # nationwide tileset, same zoom range and tiling scheme.
    tile = get_tile(14, 8794, 8595)
    assert tile is not None
    assert len(tile) > 0


def test_get_tile_returns_none_outside_the_aoi():
    assert get_tile(14, 1, 1) is None
