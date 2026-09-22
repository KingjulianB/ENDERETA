"""Command-line entrypoints for the ENDERETA pipeline.

`export-demo` just copies raw layers for the viewer. `number-district`
runs the actual pipeline (street assignment -> house numbering ->
permanent postal IDs) on buildings/streets GeoJSON files and writes both
a numbered GeoJSON (for the viewer) and a plain postal-ID/address CSV.

This does NOT include real ingestion (Open Buildings / OSM download) --
it consumes already-ingested GeoJSON. Wiring ingestion in is the next
step (see DOCS.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import geopandas as gpd

from enderata.estimate_addresses import run_estimated_addressing
from enderata.pipeline import run_pipeline, to_feature_collection
from enderata.satellite.pipeline import bbox_from_center, detect_built_up_area
from enderata.satellite.sentinel2 import LUANDA_CENTRE


def export_demo(buildings_path: str, streets_path: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(buildings_path, out / "buildings.geojson")
    shutil.copy(streets_path, out / "streets.geojson")


def number_district(
    buildings_path: str,
    streets_path: str,
    out_dir: str,
    country_code: str,
    district_code: str,
    max_distance: float | None,
) -> None:
    buildings_gdf = gpd.read_file(buildings_path)
    streets_gdf = gpd.read_file(streets_path)

    addressed = run_pipeline(
        buildings_gdf, streets_gdf, country_code, district_code, max_distance=max_distance
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with (out / "buildings.geojson").open("w", encoding="utf-8") as f:
        json.dump(to_feature_collection(addressed), f)
    shutil.copy(streets_path, out / "streets.geojson")

    with (out / "addresses.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["building_id", "postal_id", "display_address"])
        for item in addressed:
            writer.writerow([item.building_id, item.postal_id, item.display_address])

    unassigned = len(buildings_gdf) - len(addressed)
    print(f"[enderata] numbered {len(addressed)} buildings, {unassigned} unassigned (no nearby street)")


def satellite_builtup(
    lat: float,
    lon: float,
    radius_km: float,
    out_dir: str,
    max_cloud_cover: float,
    ndbi_threshold: float,
    ndvi_threshold: float,
) -> None:
    bbox = bbox_from_center(lat, lon, radius_km)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    result = detect_built_up_area(
        bbox,
        max_cloud_cover=max_cloud_cover,
        ndbi_threshold=ndbi_threshold,
        ndvi_threshold=ndvi_threshold,
        image_dir=str(out),
    )

    with (out / "built_up.geojson").open("w", encoding="utf-8") as f:
        json.dump(result.feature_collection, f)

    print(
        f"[enderata] built-up mask from Sentinel-2 scene {result.scene_id} "
        f"({result.scene_datetime}, {result.cloud_cover:.1f}% cloud, "
        f"ndbi>{ndbi_threshold} & ndvi<{ndvi_threshold}) -> "
        f"{len(result.feature_collection['features'])} polygons "
        "(coarse density signal, NOT individual buildings -- see DOCS.md). "
        f"true_colour.png / ndbi.png / ndvi.png also written to {out} for inspection."
    )


def estimate_addresses(
    lat: float,
    lon: float,
    radius_km: float,
    out_dir: str,
    country_code: str,
    district_code: str,
    spacing_m: float,
    max_points: int,
    max_distance: float | None,
) -> None:
    bbox = bbox_from_center(lat, lon, radius_km)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    result = run_estimated_addressing(
        bbox, country_code, district_code, spacing_m=spacing_m, max_points=max_points, max_distance=max_distance
    )

    with (out / "buildings.geojson").open("w", encoding="utf-8") as f:
        json.dump(to_feature_collection(result.addressed), f)
    result.streets_gdf.to_file(out / "streets.geojson", driver="GeoJSON")

    with (out / "addresses.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["building_id", "postal_id", "display_address"])
        for item in result.addressed:
            writer.writerow([item.building_id, item.postal_id, item.display_address])

    print(
        f"[enderata] estimated {result.n_estimated_buildings} building points from the built-up mask "
        f"(scene {result.built_up.scene_id}), {result.n_streets} real OSM streets, "
        f"{result.n_addressed} addressed. THESE ARE ESTIMATES, not verified building locations."
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="enderata")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-demo",
        help="Copy raw (un-numbered) GeoJSON layers into the viewer's data directory",
    )
    export_parser.add_argument("--buildings", required=True)
    export_parser.add_argument("--streets", required=True)
    export_parser.add_argument("--out", default="/data/export")

    number_parser = subparsers.add_parser(
        "number-district",
        help="Run street assignment + house numbering + postal ID generation",
    )
    number_parser.add_argument("--buildings", required=True)
    number_parser.add_argument("--streets", required=True)
    number_parser.add_argument("--out", default="/data/export")
    number_parser.add_argument("--country", default="AO")
    number_parser.add_argument("--district", default="LUA")
    number_parser.add_argument("--max-distance", type=float, default=None)

    satellite_parser = subparsers.add_parser(
        "satellite-builtup",
        help="Fetch a real Sentinel-2 scene and compute a coarse built-up-area mask (NOT building footprints)",
    )
    satellite_parser.add_argument("--lat", type=float, default=LUANDA_CENTRE[0])
    satellite_parser.add_argument("--lon", type=float, default=LUANDA_CENTRE[1])
    satellite_parser.add_argument("--radius-km", type=float, default=1.6)
    satellite_parser.add_argument("--out", default="/data/export")
    satellite_parser.add_argument("--max-cloud-cover", type=float, default=20.0)
    satellite_parser.add_argument("--ndbi-threshold", type=float, default=0.0)
    satellite_parser.add_argument("--ndvi-threshold", type=float, default=0.3)

    estimate_parser = subparsers.add_parser(
        "estimate-addresses",
        help=(
            "Estimate addresses from real OSM streets + Sentinel-2 built-up-area sampled "
            "building points (NOT real building footprints -- see DOCS.md)"
        ),
    )
    estimate_parser.add_argument("--lat", type=float, default=LUANDA_CENTRE[0])
    estimate_parser.add_argument("--lon", type=float, default=LUANDA_CENTRE[1])
    estimate_parser.add_argument("--radius-km", type=float, default=1.6)
    estimate_parser.add_argument("--out", default="/data/export")
    estimate_parser.add_argument("--country", default="AO")
    estimate_parser.add_argument("--district", default="LUA")
    estimate_parser.add_argument("--spacing-m", type=float, default=60.0)
    estimate_parser.add_argument("--max-points", type=int, default=1000)
    estimate_parser.add_argument("--max-distance", type=float, default=60.0)

    args = parser.parse_args()
    if args.command == "export-demo":
        export_demo(args.buildings, args.streets, args.out)
    elif args.command == "number-district":
        number_district(
            args.buildings, args.streets, args.out, args.country, args.district, args.max_distance
        )
    elif args.command == "satellite-builtup":
        satellite_builtup(
            args.lat,
            args.lon,
            args.radius_km,
            args.out,
            args.max_cloud_cover,
            args.ndbi_threshold,
            args.ndvi_threshold,
        )
    elif args.command == "estimate-addresses":
        estimate_addresses(
            args.lat,
            args.lon,
            args.radius_km,
            args.out,
            args.country,
            args.district,
            args.spacing_m,
            args.max_points,
            args.max_distance,
        )


if __name__ == "__main__":
    main()
