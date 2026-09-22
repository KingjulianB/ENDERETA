# Luanda vector tiles

`luanda.mbtiles` is a small (696KB), pre-generated, self-hosted vector
tile archive covering only the Luanda pilot AOI (the same bbox used
elsewhere in this project: `bbox_from_center(-8.83833, 13.23444,
1.6)`), zoom levels 0-14, OpenMapTiles schema.

**Pilot district changed from Huambo to Luanda 2026-09-22:** real,
open (CC-BY 4.0) high-resolution imagery exists for Luanda via
OpenAerialMap (a 2017 Maxar mosaic, 0.5m/pixel, verified via their live
API) -- none exists for Huambo at any usable resolution/licence (NICFI
and OSM-editor imagery layers were both checked and ruled out; see
`discrepancies.md`). The previous Huambo tileset generation notes are
kept below for reference since the process is identical.

**Generated 2026-09-22, real data, verified working:**
- Source: Angola's OSM extract from Geofabrik
  (`download.geofabrik.de/africa/angola-latest.osm.pbf`, 85MB),
  auto-downloaded by Planetiler (reused from the Huambo generation --
  Luanda is in the same country extract).
- Tool: [Planetiler](https://github.com/onthegomap/planetiler) v0.10.2
  (`planetiler.jar`, official GitHub release, not a guessed URL).
- Command actually run:
  ```
  java -Xmx4g -jar planetiler.jar \
    --area=angola \
    --bounds=13.219852,-8.852744,13.249028,-8.823916 \
    --force
  ```
- Result inspected directly (sqlite3): valid `metadata`/`tiles`
  tables, OpenMapTiles schema, 22 tiles, zoom 0-14. TMS->XYZ row
  conversion re-verified for the new location (z14 tile independently
  computed to cover Luanda's centre, 8794/8595 XYZ, matches
  tile_row=7788 in the table).
- Rendering re-verified in a real browser after the switch: caught and
  fixed a real bug specific to this new AOI -- Luanda's bbox includes
  a named water body (the bay), triggering a `water_name` vector layer
  that didn't exist in Huambo's smaller tileset and wasn't in the
  viewer's style list, showing up as an unstyled default blue marker.

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
  --bounds=13.219852,-8.852744,13.249028,-8.823916 \
  --force
cp data/output.mbtiles path/to/enderata/tiles/luanda.mbtiles
```

## Known limitation

`--bounds` clips the output, but each Geofabrik OSM extract still
needs a full country (`angola`) download to source from -- there's no
smaller pre-made Luanda-only extract on Geofabrik. Not a problem at
85MB for one-time generation.

If the AOI's vector layer composition changes (e.g. a new named water
body, a new airport nearby), double-check `viewer/map.js`'s
`vectorTileLayerStyles` covers every layer in the new tileset's
metadata JSON (`SELECT value FROM metadata WHERE name='json'`) --
anything left unstyled falls back to Leaflet's default blue marker,
as happened with `water_name` on this switch.

## Serving

`enderata/src/enderata/viz/server.py` reads tile blobs directly out of
this SQLite file at request time (`/tiles/<z>/<x>/<y>.pbf`) -- no
separate tile-server process. MBTiles stores tiles in TMS row order
(Y flipped relative to the XYZ scheme web map libraries expect); the
server route converts between the two.
