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

from enderata.pipeline import run_pipeline, to_feature_collection


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
    number_parser.add_argument("--district", default="HUA")
    number_parser.add_argument("--max-distance", type=float, default=None)

    args = parser.parse_args()
    if args.command == "export-demo":
        export_demo(args.buildings, args.streets, args.out)
    elif args.command == "number-district":
        number_district(
            args.buildings, args.streets, args.out, args.country, args.district, args.max_distance
        )


if __name__ == "__main__":
    main()
