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
"""

from __future__ import annotations

import json
import os
import shutil

import geopandas as gpd
from flask import Flask, jsonify, send_from_directory

from enderata.pipeline import run_pipeline, to_feature_collection

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
