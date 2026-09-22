"""End-to-end orchestration: streets + buildings -> numbered, addressed buildings.

Ties together street_assignment, ordering, postal_id and
address_formatter. Postal-ID sequence numbers come from a
SequenceProvider (numbering/sequence.py): by default, InMemorySequenceProvider
sorts building_id within this one run (deterministic, but only valid
for a fixed, closed input set -- see its docstring). Pass a
DbSequenceProvider (backed by the `postal_sequences` table) for a real,
growing dataset instead, so that a building_id's postal ID -- once
issued -- is never reassigned, even across separate runs that add new
buildings.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd

from enderata.numbering.address_formatter import format_address
from enderata.numbering.ordering import BuildingOnStreet, assign_house_numbers
from enderata.numbering.postal_id import generate_postal_id
from enderata.numbering.sequence import InMemorySequenceProvider, SequenceProvider
from enderata.numbering.street_assignment import Street, StreetIndex, assign_building_to_street


@dataclass(frozen=True)
class AddressedBuilding:
    building_id: str
    postal_id: str
    street_name: str
    house_number: int
    display_address: str
    longitude: float
    latitude: float
    # Optional -- only populated when buildings_gdf carries these columns
    # (real OSM buildings, ingestion/osm_buildings.py). None for the
    # synthetic fixture and estimate_addresses.py's grid-sampled points,
    # which have no OSM tags to draw from.
    building_type: str | None = None
    osm_street_name: str | None = None
    osm_housenumber: str | None = None


def _streets_from_geodataframe(streets_gdf: gpd.GeoDataFrame) -> list[Street]:
    return [
        Street(street_id=row.street_id, name=row.name, geometry=row.geometry)
        for row in streets_gdf.itertuples()
    ]


def _clean_optional(value: object) -> str | None:
    """pandas/geopandas silently turns a Python None into a float NaN
    when a GeoDataFrame column is built from a plain list mixing None
    and strings (observed directly in osm_buildings.py's output) --
    itertuples() then hands back that NaN, not None. Normalize both to
    None here rather than relying on upstream construction to avoid it."""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    return value


def run_pipeline(
    buildings_gdf: gpd.GeoDataFrame,
    streets_gdf: gpd.GeoDataFrame,
    country_code: str,
    district_code: str,
    max_distance: float | None = None,
    sequence_provider: SequenceProvider | None = None,
) -> list[AddressedBuilding]:
    streets = _streets_from_geodataframe(streets_gdf)
    street_names = {street.street_id: street.name for street in streets}
    street_index = StreetIndex(streets)

    assignments = {}
    geometries = {}
    extra_attrs = {}
    for row in buildings_gdf.itertuples():
        geometries[row.building_id] = row.geometry
        extra_attrs[row.building_id] = {
            "building_type": _clean_optional(getattr(row, "building_type", None)),
            "osm_street_name": _clean_optional(getattr(row, "osm_street_name", None)),
            "osm_housenumber": _clean_optional(getattr(row, "osm_housenumber", None)),
        }
        result = assign_building_to_street(row.geometry, street_index, max_distance=max_distance)
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

    if sequence_provider is None:
        sequence_provider = InMemorySequenceProvider(list(assignments.keys()))

    results: list[AddressedBuilding] = []
    for building_id in sorted(assignments.keys()):
        assignment = assignments[building_id]
        street_name = street_names[assignment.street_id]
        geometry = geometries[building_id]
        sequence = sequence_provider.next_sequence(building_id)
        attrs = extra_attrs[building_id]
        results.append(
            AddressedBuilding(
                building_id=building_id,
                postal_id=generate_postal_id(country_code, district_code, sequence),
                street_name=street_name,
                house_number=house_numbers[building_id],
                display_address=format_address(street_name, house_numbers[building_id], district_code),
                longitude=geometry.x,
                latitude=geometry.y,
                building_type=attrs["building_type"],
                osm_street_name=attrs["osm_street_name"],
                osm_housenumber=attrs["osm_housenumber"],
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
                    "building_type": item.building_type,
                    "osm_street_name": item.osm_street_name,
                    "osm_housenumber": item.osm_housenumber,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [item.longitude, item.latitude],
                },
            }
            for item in addressed
        ],
    }
