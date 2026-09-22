"""Assign a building to its nearest street segment.

Uses an STRtree spatial index (see StreetIndex) for nearest-street
search, and the signed cross product of (line-start -> line-end)
versus (line-start -> point) to decide which side of the street the
building sits on -- this drives the odd/even split in ordering.py.

Was a plain linear scan (min() over every street) until 2026-09-22:
correct, but O(buildings x streets) with no index -- run_pipeline()
calls this once per building against the full street list every time,
which measured ~11 minutes for 897 buildings x 268,753 streets (a
20km-radius Luanda test, see discrepancies.md/project_log.md). An
STRtree, built once per street set and reused across every building in
the run, replaces that scan.
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely import STRtree
from shapely.geometry import LineString, Point


@dataclass(frozen=True)
class Street:
    street_id: str
    name: str
    geometry: LineString


@dataclass(frozen=True)
class StreetAssignment:
    street_id: str
    distance_along_street: float
    side: str  # "even" or "odd"
    distance_to_street: float


class StreetIndex:
    """An STRtree over `streets`' geometries, built once and reused
    across many assign_building_to_street() calls -- rebuilding it per
    building would defeat the point of indexing at all."""

    def __init__(self, streets: list[Street]):
        self.streets = streets
        self._tree = STRtree([street.geometry for street in streets])

    def nearest(self, building: Point) -> Street | None:
        if not self.streets:
            return None
        idx = self._tree.nearest(building)
        if idx is None:
            return None
        return self.streets[int(idx)]


def _side_of_line(line: LineString, point: Point) -> str:
    (x1, y1), (x2, y2) = line.coords[0], line.coords[-1]
    cross = (x2 - x1) * (point.y - y1) - (y2 - y1) * (point.x - x1)
    return "even" if cross >= 0 else "odd"


def assign_building_to_street(
    building: Point, street_index: StreetIndex, max_distance: float | None = None
) -> StreetAssignment | None:
    nearest = street_index.nearest(building)
    if nearest is None:
        return None
    distance_to_street = building.distance(nearest.geometry)

    if max_distance is not None and distance_to_street > max_distance:
        return None

    return StreetAssignment(
        street_id=nearest.street_id,
        distance_along_street=nearest.geometry.project(building),
        side=_side_of_line(nearest.geometry, building),
        distance_to_street=distance_to_street,
    )
