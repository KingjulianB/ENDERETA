"""Assign a building to its nearest street segment.

Uses point-to-line distance for nearest-street search (fine at district
scale) and the signed cross product of (line-start -> line-end) versus
(line-start -> point) to decide which side of the street the building
sits on -- this drives the odd/even split in ordering.py.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def _side_of_line(line: LineString, point: Point) -> str:
    (x1, y1), (x2, y2) = line.coords[0], line.coords[-1]
    cross = (x2 - x1) * (point.y - y1) - (y2 - y1) * (point.x - x1)
    return "even" if cross >= 0 else "odd"


def assign_building_to_street(
    building: Point, streets: list[Street], max_distance: float | None = None
) -> StreetAssignment | None:
    if not streets:
        return None

    nearest = min(streets, key=lambda street: building.distance(street.geometry))
    distance_to_street = building.distance(nearest.geometry)

    if max_distance is not None and distance_to_street > max_distance:
        return None

    return StreetAssignment(
        street_id=nearest.street_id,
        distance_along_street=nearest.geometry.project(building),
        side=_side_of_line(nearest.geometry, building),
        distance_to_street=distance_to_street,
    )
