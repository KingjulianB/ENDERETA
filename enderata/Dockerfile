ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

# System deps: Postgres + PostGIS, plus GDAL/GEOS/PROJ for geopandas/osmnx.
# NOT build-tested in this session (no Docker runtime available here) --
# run `docker build .` and fix whatever the geopandas/GDAL compile step
# surfaces before relying on this image. See DOCS.md.
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql postgresql-contrib postgis \
        gdal-bin libgdal-dev gcc curl jq \
    && rm -rf /var/lib/apt/lists/*

# bashio gives addon scripts access to the HA supervisor's config/options.
RUN curl -sSL https://raw.githubusercontent.com/hassio-addons/bashio/master/install.sh | bash

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY viewer ./viewer
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENV PYTHONPATH=/app/src

CMD ["/run.sh"]
