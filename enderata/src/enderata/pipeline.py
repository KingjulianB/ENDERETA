"""End-to-end orchestration: streets + buildings -> numbered, addressed buildings.

Ties together street_assignment, ordering, postal_id and
address_formatter. Postal-ID sequence numbers are assigned by sorting on
building_id (a stable, deterministic order) rather than on array
position or dict iteration order, so re-running the pipeline on the same
input always yields the same postal IDs -- the "permanent, never
reassigned" guarantee the business plan requires.

Known limitation: sequencing by sorted building_id is only valid for a
fixed, closed input set. A real deployment must replace it with a
persistent counter (a DB sequence keyed by building_id) so that IDs
survive new buildings being added later without shifting existing ones.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd

from enderata.numbering.address_formatter import format_address
from enderata.numbering.ordering import BuildingOnStreet, assign_house_numbers
from enderata.numbering.postal_id import generate_postal_id
from enderata.numbering.street_assignment import Street, assign_building_to_street


@dataclass(frozen=True)
class AddressedBuilding:
    building_id: str
    postal_id: str
    street_name: str
    house_number: int
    display_address: str
    longitude: float
    latitude: float


def _streets_from_geodataframe(streets_gdf: gpd.GeoDataFrame) -> list[Street]:
    return [
        Street(street_id=row.street_id, name=row.name, geometry=row.geometry)
        for row in streets_gdf.itertuples()
    ]


def run_pipeline(
    buildings_gdf: gpd.GeoDataFrame,
    streets_gdf: gpd.GeoDataFrame,
    country_code: str,
    district_code: str,
    max_distance: float | None = None,
) -> list[AddressedBuilding]:
    streets = _streets_from_geodataframe(streets_gdf)
    street_names = {street.street_id: street.name for street in streets}

    assignments = {}
    geometries = {}
    for row in buildings_gdf.itertuples():
        geometries[row.building_id] = row.geometry
        result = assign_building_to_street(row.geometry, streets, max_distance=max_distance)
        if result is not None:
            assignments[row.building_id] = result

    on_street = [
        BuildingOnStreet(
            building_id=building_id,
            street_id=assignment.street_id,
            distance_along_street=assignment.distance_along_street,
            side=assignment.side,
        )
        for building_id, assignment in assignments.items()
    ]
    house_numbers = {hn.building_id: hn.number for hn in assign_house_numbers(on_street)}

    # Deterministic, input-order-independent sequencing (see module docstring).
    ordered_ids = sorted(assignments.keys())

    results: list[AddressedBuilding] = []
    for sequence, building_id in enumerate(ordered_ids, start=1):
        assignment = assignments[building_id]
        street_name = street_names[assignment.street_id]
        geometry = geometries[building_id]
        results.append(
            AddressedBuilding(
                building_id=building_id,
                postal_id=generate_postal_id(country_code, district_code, sequence),
                street_name=street_name,
                house_number=house_numbers[building_id],
                display_address=format_address(street_name, house_numbers[building_id], district_code),
                longitude=geometry.x,
                latitude=geometry.y,
            )
        )
    return results


def to_feature_collection(addressed: list[AddressedBuilding]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "building_id": item.building_id,
                    "postal_id": item.postal_id,
                    "street_name": item.street_name,
                    "house_number": item.house_number,
                    "display_address": item.display_address,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [item.longitude, item.latitude],
                },
            }
            for item in addressed
        ],
    }
