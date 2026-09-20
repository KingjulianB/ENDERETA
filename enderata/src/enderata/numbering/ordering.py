"""Order buildings along a street and assign Western-style house numbers.

Buildings assigned to the same street are grouped by side (even/odd,
per street_assignment.side) and numbered in ascending order of distance
along the street line, incrementing by 2 -- e.g. odd side: 1, 3, 5...;
even side: 2, 4, 6...
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildingOnStreet:
    building_id: str
    street_id: str
    distance_along_street: float
    side: str


@dataclass(frozen=True)
class HouseNumber:
    building_id: str
    street_id: str
    number: int


def assign_house_numbers(buildings: list[BuildingOnStreet]) -> list[HouseNumber]:
    grouped: dict[tuple[str, str], list[BuildingOnStreet]] = defaultdict(list)
    for building in buildings:
        grouped[(building.street_id, building.side)].append(building)

    results: list[HouseNumber] = []
    for (street_id, side), group in grouped.items():
        start = 2 if side == "even" else 1
        ordered = sorted(group, key=lambda b: b.distance_along_street)
        for index, building in enumerate(ordered):
            results.append(
                HouseNumber(
                    building_id=building.building_id,
                    street_id=street_id,
                    number=start + index * 2,
                )
            )
    return results
