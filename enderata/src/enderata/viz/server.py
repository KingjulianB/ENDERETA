"""Minimal web server for the Luanda POC demo (pilot district changed
from Huambo to Luanda 2026-09-22 -- see discrepancies.md).

Serves the static Leaflet viewer and the exported GeoJSON layers. Runs
behind Home Assistant ingress -- all asset references in the viewer
must stay relative so the ingress path prefix does not break them.

Also exposes /api/load-demo, which runs the numbering pipeline against
the bundled synthetic fixture and writes the result to DATA_DIR. This
exists because the standard "Terminal & SSH" HA add-on has no docker
CLI access (it's sandboxed, no docker socket), so `docker exec` isn't
available to most users -- the demo has to be triggerable from the web
UI itself, not just the CLI.

Also exposes /api/load-satellite, which fetches a real Sentinel-2 scene
over Luanda (via the public AWS Earth Search STAC catalog -- needs
outbound internet from wherever this add-on runs) and computes a coarse
NDBI+NDVI built-up mask. This is NOT building-footprint detection (see
enderata.satellite.built_up's docstring) -- it's a free, legally-clean
density/extent signal, kept as a separate layer from the numbered
buildings so the two are never visually confused.

Also exposes /api/estimate-addresses, which chains real OSM streets +
the Sentinel-2 built-up mask's sampled building points (see
enderata.estimate_addresses) through the numbering pipeline. Output is
written to its own estimated_buildings.geojson/estimated_streets.geojson
files (not buildings.geojson/streets.geojson) so it never gets confused
with the synthetic demo fixture or overwrites it.
"""

from __future__ import annotations

import json
import os
import shutil

import geopandas as gpd
from flask import Flask, jsonify, request, send_from_directory

from enderata.estimate_addresses import run_estimated_addressing
from enderata.pipeline import run_pipeline, to_feature_collection
from enderata.satellite.pipeline import bbox_from_center, detect_built_up_area
from enderata.satellite.sentinel2 import LUANDA_CENTRE
from enderata.tileserver import get_tile

VIEWER_DIR = os.environ.get("ENDERATA_VIEWER_DIR", "/app/viewer")
DATA_DIR = os.environ.get("ENDERATA_DATA_DIR", "/data/export")
FIXTURES_DIR = os.environ.get(
    "ENDERATA_FIXTURES_DIR", "/app/fixtures/synthetic_sample"
)

app = Flask(__name__, static_folder=None)


@app.after_request
def disable_viewer_caching(response):
    # The viewer is iframed through HA ingress, which combined with
    # normal browser caching has repeatedly served a stale index.html/
    # map.js after an add-on update -- e.g. a button added to the HTML
    # silently did nothing because the cached JS predated it. Rather
    # than relying on users to hard-refresh after every update, force
    # revalidation on every request for the page and its script.
    if request.path in ("/", "/index.html", "/map.js"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.route("/")
def index():
    return send_from_directory(VIEWER_DIR, "index.html")


@app.route("/<path:filename>")
def viewer_assets(filename):
    return send_from_directory(VIEWER_DIR, filename)


@app.route("/data/<path:filename>")
def data_files(filename):
    return send_from_directory(DATA_DIR, filename)


@app.route("/tiles/<int:z>/<int:x>/<int:y>.pbf")
def tiles(z, x, y):
    # See tiles/README.md: luanda.mbtiles is pre-generated (Planetiler,
    # offline), this just reads the matching blob out of it.
    try:
        tile = get_tile(z, x, y)
    except FileNotFoundError as exc:
        # tileserver already logs this once at import time; log again per
        # request (rate-limited by simply not looping) so it's impossible
        # to miss in the add-on log when the basemap is blank.
        print(f"[server] /tiles/{z}/{x}/{y}.pbf failed: {exc}")
        return "", 404
    if tile is None:
        return "", 204
    response = app.response_class(tile, mimetype="application/x-protobuf")
    response.headers["Content-Encoding"] = "gzip"  # MBTiles stores tiles pre-gzipped
    return response


@app.route("/api/load-demo", methods=["POST"])
def load_demo():
    buildings_path = os.path.join(FIXTURES_DIR, "buildings.geojson")
    streets_path = os.path.join(FIXTURES_DIR, "streets.geojson")

    buildings_gdf = gpd.read_file(buildings_path)
    streets_gdf = gpd.read_file(streets_path)
    addressed = run_pipeline(buildings_gdf, streets_gdf, "AO", "LUA")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "buildings.geojson"), "w", encoding="utf-8") as f:
        json.dump(to_feature_collection(addressed), f)
    shutil.copy(streets_path, os.path.join(DATA_DIR, "streets.geojson"))

    return jsonify({"status": "ok", "count": len(addressed)})


@app.route("/api/load-satellite", methods=["POST"])
def load_satellite():
    """Runs the built-up detection and also saves true_colour.png,
    ndbi.png and ndvi.png into DATA_DIR (served by /data/<filename>
    above) so the viewer can overlay the actual processed imagery, not
    just the final mask -- lets a human judge whether ndbi_threshold/
    ndvi_threshold (optionally overridden in the POST body) need
    adjusting.
    """
    body = request.get_json(silent=True) or {}
    ndbi_threshold = float(body.get("ndbi_threshold", 0.0))
    ndvi_threshold = float(body.get("ndvi_threshold", 0.3))

    lat, lon = LUANDA_CENTRE
    bbox = bbox_from_center(lat, lon, radius_km=1.6)

    try:
        result = detect_built_up_area(
            bbox,
            ndbi_threshold=ndbi_threshold,
            ndvi_threshold=ndvi_threshold,
            image_dir=DATA_DIR,
        )
    except RuntimeError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "built_up.geojson"), "w", encoding="utf-8") as f:
        json.dump(result.feature_collection, f)

    return jsonify(
        {
            "status": "ok",
            "count": len(result.feature_collection["features"]),
            "scene_id": result.scene_id,
            "scene_datetime": result.scene_datetime,
            "cloud_cover": result.cloud_cover,
            "bounds_wgs84": list(result.bounds_wgs84),
            "ndbi_threshold": result.ndbi_threshold,
            "ndvi_threshold": result.ndvi_threshold,
        }
    )


@app.route("/api/estimate-addresses", methods=["POST"])
def estimate_addresses_route():
    """Real OSM streets + Sentinel-2 built-up-sampled building points ->
    numbering pipeline. THESE BUILDING LOCATIONS ARE ESTIMATES (a grid
    sample inside a 10m/pixel built-up mask), not verified footprints --
    see enderata.satellite.building_estimate's docstring. Body may
    override spacing_m/max_points/max_distance; defaults match the CLI.
    """
    body = request.get_json(silent=True) or {}
    spacing_m = float(body.get("spacing_m", 60.0))
    max_points = int(body.get("max_points", 1000))
    max_distance = body.get("max_distance", 60.0)
    max_distance = float(max_distance) if max_distance is not None else None

    lat, lon = LUANDA_CENTRE
    bbox = bbox_from_center(lat, lon, radius_km=1.6)

    try:
        result = run_estimated_addressing(
            bbox, "AO", "LUA", spacing_m=spacing_m, max_points=max_points, max_distance=max_distance
        )
    except RuntimeError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "estimated_buildings.geojson"), "w", encoding="utf-8") as f:
        json.dump(to_feature_collection(result.addressed), f)
    result.streets_gdf.to_file(os.path.join(DATA_DIR, "estimated_streets.geojson"), driver="GeoJSON")

    return jsonify(
        {
            "status": "ok",
            "count": result.n_addressed,
            "n_streets": result.n_streets,
            "n_estimated_buildings": result.n_estimated_buildings,
            "scene_id": result.built_up.scene_id,
            "scene_datetime": result.built_up.scene_datetime,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
