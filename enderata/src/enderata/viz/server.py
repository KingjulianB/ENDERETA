"""Minimal web server for the Huambo POC demo.

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
over Huambo (via the public AWS Earth Search STAC catalog -- needs
outbound internet from wherever this add-on runs) and computes a coarse
NDBI+NDVI built-up mask. This is NOT building-footprint detection (see
enderata.satellite.built_up's docstring) -- it's a free, legally-clean
density/extent signal, kept as a separate layer from the numbered
buildings so the two are never visually confused.
"""

from __future__ import annotations

import json
import os
import shutil

import geopandas as gpd
from flask import Flask, jsonify, request, send_from_directory

from enderata.pipeline import run_pipeline, to_feature_collection
from enderata.satellite.pipeline import bbox_from_center, detect_built_up_area
from enderata.satellite.sentinel2 import HUAMBO_CENTRE

VIEWER_DIR = os.environ.get("ENDERATA_VIEWER_DIR", "/app/viewer")
DATA_DIR = os.environ.get("ENDERATA_DATA_DIR", "/data/export")
FIXTURES_DIR = os.environ.get(
    "ENDERATA_FIXTURES_DIR", "/app/fixtures/synthetic_sample"
)

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(VIEWER_DIR, "index.html")


@app.route("/<path:filename>")
def viewer_assets(filename):
    return send_from_directory(VIEWER_DIR, filename)


@app.route("/data/<path:filename>")
def data_files(filename):
    return send_from_directory(DATA_DIR, filename)


@app.route("/api/load-demo", methods=["POST"])
def load_demo():
    buildings_path = os.path.join(FIXTURES_DIR, "buildings.geojson")
    streets_path = os.path.join(FIXTURES_DIR, "streets.geojson")

    buildings_gdf = gpd.read_file(buildings_path)
    streets_gdf = gpd.read_file(streets_path)
    addressed = run_pipeline(buildings_gdf, streets_gdf, "AO", "HUA")

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

    lat, lon = HUAMBO_CENTRE
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
