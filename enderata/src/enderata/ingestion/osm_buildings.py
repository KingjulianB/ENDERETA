"""Fetch real building footprints from OpenStreetMap for an AOI via
osmnx (Overpass API under the hood), shaped for
`enderata.pipeline.run_pipeline` (`building_id`, Point `geometry`).

Unlike `satellite/building_estimate.py`'s grid-sampled points, these
are REAL, individually-mapped buildings -- but OSM's building coverage
is volunteer-mapped and incomplete, not exhaustive like a satellite-
derived dataset (Google Open Buildings) would be. Verified 2026-09-22
against the real Luanda AOI (bbox_from_center on LUANDA_CENTRE, 1.6km
radius): 749 real buildings (736 polygons + 13 single-node buildings),
many carrying existing addr:housenumber/addr:street/name tags (not
used here -- this project assigns its own addresses, it doesn't copy
OSM's).

A polygon's centroid is used as its building_id's point location.
Shapely computes this planar even in EPSG:4326 (degrees); for
building-sized polygons the resulting distortion is negligible --
consistent with the equirectangular approximations already used
elsewhere in this codebase (see satellite/pipeline.py's
bbox_from_center), not something this module treats differently.
"""

from __future__ import annotations

import warnings

import geopandas as gpd
import osmnx as ox


def load_osm_buildings(bbox_wgs84: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Fetch real OSM-mapped buildings within `bbox_wgs84` (west,
    south, east, north) and return them shaped for `run_pipeline`."""
    features = ox.features_from_bbox(bbox_wgs84, tags={"building": True})

    building_ids = [f"osm-{element}-{osm_id}" for element, osm_id in features.index]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        points = features.geometry.centroid

    buildings = gpd.GeoDataFrame(
        {"building_id": building_ids, "geometry": points.values},
        crs=features.crs,
    )
    return buildings
