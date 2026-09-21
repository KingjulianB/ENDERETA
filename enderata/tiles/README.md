# Huambo vector tiles

`huambo.mbtiles` is a small (491KB), pre-generated, self-hosted vector
tile archive covering only the Huambo pilot AOI (the same bbox used
elsewhere in this project: `bbox_from_center(-12.77611, 15.73917,
1.6)`), zoom levels 0-14, OpenMapTiles schema.

**Generated 2026-09-21, real data, verified working:**
- Source: Angola's OSM extract from Geofabrik
  (`download.geofabrik.de/africa/angola-latest.osm.pbf`, 85MB),
  auto-downloaded by Planetiler.
- Tool: [Planetiler](https://github.com/onthegomap/planetiler) v0.10.2
  (`planetiler.jar`, official GitHub release, not a guessed URL).
- Command actually run:
  ```
  java -Xmx4g -jar planetiler.jar \
    --area=angola \
    --bounds=15.72439,-12.790524,15.75395,-12.761696 \
    --force
  ```
- Result inspected directly (sqlite3): valid `metadata`/`tiles`
  tables, OpenMapTiles schema (`transportation`, `building`, `water`,
  `landuse`, `place`, `poi`, etc. layers), 24 tiles, zoom 0-14.

## Why this approach, not a live tile-rendering server

The default Planetiler profile also pulls ~1.4GB of global auxiliary
data (natural_earth, water_polygons, lake_centerlines) needed for
consistent styling at low zoom levels worldwide -- fine for a one-time
generation step run on a dev machine, completely inappropriate to run
inside the lightweight HA add-on container itself (no Java, no extra
1.4GB downloads, no long-running generation job on every start).
Generating once here and shipping only the resulting small `.mbtiles`
keeps the add-on itself simple: it just needs to read tile blobs out
of a small SQLite file, no Java or Planetiler at runtime.

## Regenerating (when OSM data needs refreshing)

Requires a JDK (any recent version; verified with OpenJDK 25) on
whatever machine does the regeneration -- NOT inside the add-on.

```bash
curl -sL -o planetiler.jar \
  https://github.com/onthegomap/planetiler/releases/download/v0.10.2/planetiler.jar
java -Xmx4g -jar planetiler.jar \
  --area=angola \
  --bounds=15.72439,-12.790524,15.75395,-12.761696 \
  --force
cp data/output.mbtiles path/to/enderata/tiles/huambo.mbtiles
```

## Known limitation

`--bounds` clips PostGIS geometries used, but each Geofabrik OSM
extract still needs a full country (`angola`) download to source from
-- there's no smaller pre-made Huambo-only extract on Geofabrik. Not a
problem at 85MB for one-time generation, but note this if the AOI ever
needs to move to a different country.

## Serving

`enderata/src/enderata/viz/server.py` reads tile blobs directly out of
this SQLite file at request time (`/tiles/<z>/<x>/<y>.pbf`) -- no
separate tile-server process. MBTiles stores tiles in TMS row order
(Y flipped relative to the XYZ scheme web map libraries expect); the
server route converts between the two.
