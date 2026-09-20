"""Minimal web server for the Huambo POC demo.

Serves the static Leaflet viewer and the exported GeoJSON layers. Runs
behind Home Assistant ingress -- all asset references in the viewer
must stay relative so the ingress path prefix does not break them.
"""

from __future__ import annotations

import os

from flask import Flask, send_from_directory

VIEWER_DIR = os.environ.get("ENDERATA_VIEWER_DIR", "/app/viewer")
DATA_DIR = os.environ.get("ENDERATA_DATA_DIR", "/data/export")

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
