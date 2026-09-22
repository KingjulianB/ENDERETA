import os
from pathlib import Path

os.environ.setdefault(
    "ENDERATA_MBTILES_PATH",
    str(Path(__file__).parent.parent.parent / "tiles" / "luanda.mbtiles"),
)

from enderata.tileserver import get_metadata, get_tile  # noqa: E402


def test_get_metadata_reports_the_real_luanda_bounds():
    meta = get_metadata()
    assert meta["minzoom"] == "0"
    assert meta["maxzoom"] == "14"
    assert meta["bounds"].startswith("13.2")  # Luanda AOI, not some other place


def test_get_tile_returns_bytes_for_a_known_real_tile():
    # z14/x8794/y8595 independently verified (see tileserver.py) to
    # cover Luanda's actual centre coordinate.
    tile = get_tile(14, 8794, 8595)
    assert tile is not None
    assert len(tile) > 0


def test_get_tile_returns_none_outside_the_aoi():
    assert get_tile(14, 1, 1) is None
