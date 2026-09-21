"""Serves vector tiles directly out of the pre-generated Huambo MBTiles
file (tiles/huambo.mbtiles -- see tiles/README.md for how it was
built with Planetiler). No Planetiler/Java at runtime: MBTiles is just
a SQLite database, this does a read-only lookup per request.

MBTiles stores tiles in TMS row order (Y=0 at the south), while web map
libraries (MapLibre, Leaflet) request tiles in XYZ order (Y=0 at the
north) -- get_tile() converts between the two. Verified against the
real generated file: at z14, the tile independently computed to cover
Huambo's centre (8908, 8778 XYZ) matches tile_row=7605 in the MBTiles
table via xyz_y = (2**z - 1) - tms_y = 16383 - 7605 = 8778.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

MBTILES_PATH = os.environ.get("ENDERATA_MBTILES_PATH", "/app/tiles/huambo.mbtiles")


def _connect() -> sqlite3.Connection:
    if not Path(MBTILES_PATH).exists():
        raise FileNotFoundError(f"MBTiles file not found: {MBTILES_PATH}")
    # Read-only URI connection -- this file is a build artifact, nothing
    # in this process should ever write to it.
    return sqlite3.connect(f"file:{MBTILES_PATH}?mode=ro", uri=True)


def get_tile(z: int, x: int, y: int) -> bytes | None:
    """Return the gzip-compressed PBF tile blob for XYZ (z, x, y), or
    None if that tile has no data (e.g. outside the Huambo AOI)."""
    tms_y = (2**z - 1) - y
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
            (z, x, tms_y),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_metadata() -> dict[str, str]:
    conn = _connect()
    try:
        return dict(conn.execute("SELECT name, value FROM metadata").fetchall())
    finally:
        conn.close()
