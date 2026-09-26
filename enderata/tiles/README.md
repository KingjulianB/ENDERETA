# Angola vector tiles (nationwide)

`angola.mbtiles` is a pre-generated, self-hosted vector tile archive
covering **the whole country** (bounds `10.53848,-18.06508,24.10297,-4.32792`
-- Cabinda's exclave in the north to the southern border), zoom levels
0-14, OpenMapTiles schema, 154MB, 298,207 tiles.

**2026-09-26: replaced the earlier Luanda-only `luanda.mbtiles`
(696KB, a single ~15x18km AOI)** -- user: "il s'agissait de faire le
system sur tout l'angola" (the addressing/satellite routes already
work for any Angolan place via `aoi.py::load_aoi()`, but the basemap
itself was still clipped to Luanda; this closes that gap). Both files
were built from the exact same Geofabrik source extract, so this is
purely a re-run without the old `--bounds` clip, not a data-source
change.

## Generated 2026-09-26, real data, verified working

- Source: Angola's OSM extract from Geofabrik
  (`download.geofabrik.de/africa/angola-latest.osm.pbf`, 85MB) --
  reused the copy already cached from the original Luanda-only
  generation (Planetiler auto-downloads/caches it under
  `data/sources/`).
- Tool: [Planetiler](https://github.com/onthegomap/planetiler) v0.10.2
  (`planetiler.jar`, official GitHub release).
- Command actually run (no `--bounds` this time -- omitting it makes
  Planetiler tile the OSM data's own full extent, i.e. the whole
  country, instead of clipping to a sub-region):
  ```
  java -Xmx4g -jar planetiler.jar --area=angola --force
  ```
- Result: 53s total (12s archive-write phase), 298,207 tiles, 4,346,539
  features, 154MB output. Metadata inspected directly (sqlite3):
  `bounds` = whole-Angola extent, `minzoom`/`maxzoom` unchanged (0/14),
  vector layer list unchanged from the Luanda-only build (aerodrome_label,
  aeroway, boundary, building, housenumber, landcover, landuse,
  mountain_peak, park, place, poi, transportation, transportation_name,
  water, water_name, waterway) -- confirmed every one is still covered
  by `viewer/map.js`'s `vectorTileLayerStyles`, so no new unstyled-layer
  regression (the `water_name` bug hit on the original Huambo->Luanda
  switch, see the incident below, doesn't recur here).
- TMS->XYZ tile lookup re-verified: z14/x8794/y8595 (Luanda's centre,
  the same tile checked on the original build) still resolves to real
  data in the nationwide file, since it uses the same tiling scheme,
  just a larger extent.

## Why this approach, not a live tile-rendering server

The default Planetiler profile also pulls ~1.4GB of global auxiliary
data (natural_earth, water_polygons, lake_centerlines) needed for
consistent styling at low zoom levels worldwide -- fine for a one-time
generation step run on a dev machine, completely inappropriate to run
inside the lightweight HA add-on container itself (no Java, no extra
1.4GB downloads, no long-running generation job on every start).
Generating once here and shipping only the resulting `.mbtiles` keeps
the add-on itself simple: it just needs to read tile blobs out of a
small SQLite file, no Java or Planetiler at runtime. At 154MB for the
whole country, this is still far smaller than trying to do the
equivalent for a raster (photo) basemap -- see discrepancies.md's
"Nationwide expansion" entry for why full-country satellite imagery
stays fetched on demand per place instead of pre-rendered the same way.

## Regenerating (when OSM data needs refreshing)

Requires a JDK (any recent version; verified with OpenJDK 25) on
whatever machine does the regeneration -- NOT inside the add-on.

```bash
curl -sL -o planetiler.jar \
  https://github.com/onthegomap/planetiler/releases/download/v0.10.2/planetiler.jar
java -Xmx4g -jar planetiler.jar --area=angola --force
cp data/output.mbtiles path/to/enderata/tiles/angola.mbtiles
```

Omitting `--bounds` is what makes this nationwide; passing one back in
(as the original Luanda-only build did) would re-clip to a sub-region
if a smaller file is ever needed again for some reason.

## Known limitation

Each Geofabrik OSM extract is a whole-country download -- there's no
smaller pre-made regional extract on Geofabrik for Angola. Not a
problem at 85MB for one-time generation, and no longer relevant to
output size now that the whole country is tiled anyway.

If Angola's OSM data ever introduces a genuinely new vector layer type
(rare -- OpenMapTiles' schema is fixed), double-check `viewer/map.js`'s
`vectorTileLayerStyles` covers it (`SELECT value FROM metadata WHERE
name='json'` lists every layer in the current file) -- anything left
unstyled falls back to Leaflet's default blue marker, as happened with
`water_name` on the original Huambo-to-Luanda switch (kept below for
reference).

### Historical incident (Huambo -> Luanda switch, 2026-09-22)

Rendering broke after that switch: Luanda's bbox includes a named water
body (the bay), triggering a `water_name` vector layer that didn't
exist in Huambo's smaller tileset and wasn't in the viewer's style
list, showing up as an unstyled default blue marker. Fixed by adding
`water_name: HIDDEN` to `map.js`. Confirmed not an issue for this
nationwide build since `water_name` was already in the style list by
then.

## Serving

`enderata/src/enderata/tileserver.py` reads tile blobs directly out of
this SQLite file at request time (`/tiles/<z>/<x>/<y>.pbf`, routed
through `viz/server.py`) -- no separate tile-server process. MBTiles
stores tiles in TMS row order (Y flipped relative to the XYZ scheme web
map libraries expect); the server route converts between the two.

## Deployment (2026-09-26): NOT shipped in the Docker image

At 147MB (git's compressed blob size), `angola.mbtiles` exceeds
GitHub's hard 100MB per-file limit -- a real push was rejected
(`GH001: Large files detected`). Rather than pull in Git LFS or shrink
the tileset (both considered, see project_log.md #24/discrepancies.md),
the user chose to deploy this specific file straight to the add-on's
own persistent storage over SSH, bypassing git/the Docker image
entirely for this one file:

```bash
scp enderata/tiles/angola.mbtiles \
  jarvis@<ha-host>:/mnt/data/supervisor/apps/data/<addon-container-id>/tiles/angola.mbtiles
```

(`<addon-container-id>` found via `sudo docker inspect
app_<id>_enderata --format '{{range .Mounts}}{{.Source}} ->
{{.Destination}}{{println}}{{end}}'` on the HA host -- the container's
`/data` maps to `/mnt/data/supervisor/apps/data/<id>` there.)

`run.sh` checks for `/data/tiles/angola.mbtiles` at container start and
points `ENDERATA_MBTILES_PATH` at it if present, overriding
`tileserver.py`'s image-baked default (`/app/tiles/angola.mbtiles`,
which won't exist in the image unless this file is ever added back to
git some other way, e.g. LFS). `/data` is the add-on's normal
persistent volume (same one used for Postgres/`export`), so this
survives container restarts and add-on updates -- it just needs
re-copying if the tileset itself is ever regenerated.
