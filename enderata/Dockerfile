# Fixed, multi-arch base (amd64 + aarch64) -- deliberately NOT using HA
# Supervisor's ARG BUILD_FROM/build.yaml mechanism: Supervisor's
# build.yaml validation rejects unqualified official image names (e.g.
# "python:3.12-slim-bookworm" with no namespace), silently falls back to
# its own Alpine base image, and the apt-based layer below then fails
# with "apt-get: not found". Hardcoding FROM here sidesteps that
# validation entirely, per Supervisor's own deprecation notice ("move
# build parameters into the Dockerfile directly").
FROM python:3.12-slim-bookworm

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

# System deps: Postgres + PostGIS, plus GDAL/GEOS/PROJ for geopandas/osmnx.
# NOTE: the generic "postgis" package is client tools/loaders only --
# it does NOT provide postgis.control, so `CREATE EXTENSION postgis`
# fails with "extension is not available" even though "postgis" is
# installed (seen on a real HA run). The versioned
# postgresql-15-postgis-3 package is what actually ships the server
# extension for Debian bookworm's default PostgreSQL 15.
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql postgresql-contrib postgresql-15-postgis-3 postgis \
        gdal-bin libgdal-dev gcc curl jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY viewer ./viewer
COPY tests/fixtures/synthetic_sample ./fixtures/synthetic_sample
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENV PYTHONPATH=/app/src

CMD ["/run.sh"]
