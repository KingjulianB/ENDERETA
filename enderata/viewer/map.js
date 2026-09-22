// No third-party raster basemap tiles: OpenStreetMap's tile usage
// policy explicitly forbids using tile.openstreetmap.org from a
// packaged/distributed app without prior OSMF sysadmin approval
// (osm.wiki/Blocked) -- confirmed blocked with a 403 on a real run.
// Instead, /tiles/{z}/{x}/{y}.pbf serves self-hosted vector tiles read
// straight out of tiles/luanda.mbtiles (built offline with Planetiler
// -- see tiles/README.md), covering only the Luanda pilot AOI.
// Luanda city centre -- verified 2026-09-22 (Wikipedia, cross-checked
// against a real Sentinel-2 scene: dense urban core, airport visible).
// Pilot district changed from Huambo to Luanda this date -- see
// discrepancies.md (real open high-res imagery exists for Luanda via
// OpenAerialMap, none for Huambo).
const map = L.map("map", { attributionControl: false }).setView(
  [-8.83833, 13.23444],
  14
);

// Leaflet.VectorGrid (not a MapLibre migration) so everything else
// below -- demo layers, satellite overlays, the threshold panel --
// stays exactly as already built and tested; this only adds one more
// Leaflet layer. Known limitation: VectorGrid renders geometry, not
// text labels, so road/place names from the tileset are not drawn.
// Leaflet.VectorGrid falls back to Leaflet's default blue path/marker
// style for any OpenMapTiles layer not listed here -- on a real run
// this showed up as stray blue circles/lines (housenumber points, poi
// points, etc.) that don't belong in a basemap. HIDDEN suppresses
// those explicitly rather than leaving them to the default.
const HIDDEN = { radius: 0, weight: 0, opacity: 0, fillOpacity: 0, fill: false, stroke: false };
// Fill layers use fillOpacity: 1 with a pre-chosen light colour, NOT a
// translucent colour -- OpenMapTiles' landcover/landuse/building layers
// are made of many small, sometimes-overlapping polygons (real OSM
// data), and semi-transparent fills stack: N overlapping 0.35-opacity
// shapes combine toward 1-(1-0.35)^N, which reaches near-opaque within
// a handful of overlaps. That produced a solid, over-saturated blob
// with dark cell-like seams at polygon edges on a real run (screenshot)
// -- an opacity-stacking artifact, not a one-off rendering glitch.
// Opaque fills in colours already chosen to look pale sidestep it
// entirely regardless of how much the source geometry overlaps.
L.vectorGrid
  .protobuf("tiles/{z}/{x}/{y}.pbf", {
    maxNativeZoom: 14,
    vectorTileLayerStyles: {
      water: { fill: true, fillColor: "#bcdcec", fillOpacity: 1, stroke: false },
      waterway: { color: "#bcdcec", weight: 1.5 },
      landcover: { fill: true, fillColor: "#eef1e6", fillOpacity: 1, stroke: false },
      landuse: { fill: true, fillColor: "#eee9dd", fillOpacity: 1, stroke: false },
      park: { fill: true, fillColor: "#dcebd3", fillOpacity: 1, stroke: false },
      building: { fill: true, fillColor: "#e4ded1", fillOpacity: 1, stroke: true, color: "#cfc7b8", weight: 0.5 },
      transportation: (properties) => ({
        color: "#ffffff",
        weight: properties.class === "motorway" || properties.class === "trunk" ? 2.5 : 1,
        opacity: 0.9,
      }),
      boundary: { color: "#9a9a9a", weight: 0.5, dashArray: [2, 2] },
      // Rendered as raw geometry (no label placement/text in
      // VectorGrid) they're just noise -- hide rather than show as
      // unstyled default markers/lines.
      housenumber: HIDDEN,
      poi: HIDDEN,
      place: HIDDEN,
      aeroway: HIDDEN,
      aerodrome_label: HIDDEN,
      mountain_peak: HIDDEN,
      transportation_name: HIDDEN,
      // Not present in Huambo's small tileset (no named water bodies
      // in that bbox) -- Luanda's bbox includes the bay, which does
      // have one, and it showed up as an unstyled default blue marker
      // on a real render before this was added.
      water_name: HIDDEN,
    },
    interactive: false,
  })
  .addTo(map);

let bounds = L.latLngBounds([]);
const activeLayers = [];

function loadLayer(url, style) {
  // cache-bust: the load-demo button rewrites these files in place, and
  // browsers otherwise happily serve a stale cached copy of the old ones
  fetch(`${url}?t=${Date.now()}`)
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data) return;
      const layer = L.geoJSON(data, style).addTo(map);
      activeLayers.push(layer);
      const layerBounds = layer.getBounds();
      if (layerBounds.isValid()) {
        bounds.extend(layerBounds);
        map.fitBounds(bounds, { padding: [24, 24] });
      }
    })
    .catch(() => console.warn(`ENDERETA: no data yet at ${url}`));
}

function loadAllLayers() {
  activeLayers.splice(0).forEach((layer) => map.removeLayer(layer));
  loadLayer("data/streets.geojson", { style: { color: "#2a6f97", weight: 2 } });
  loadLayer("data/buildings.geojson", {
    pointToLayer: (feature, latlng) =>
      L.circleMarker(latlng, { radius: 5, color: "#d1495b", fillOpacity: 0.9 }),
    onEachFeature: (feature, layer) => {
      const props = feature.properties || {};
      if (props.display_address) layer.bindPopup(props.display_address);
    },
  });
}

function clearDemoLayers() {
  // Only removes the layers from the map -- the underlying
  // buildings.geojson/streets.geojson on disk are left alone, so
  // "Load demo data" still works again afterwards.
  activeLayers.splice(0).forEach((layer) => map.removeLayer(layer));
  bounds = L.latLngBounds([]);
}

loadAllLayers();

const loadDemoButton = document.getElementById("load-demo");
loadDemoButton.addEventListener("click", () => {
  loadDemoButton.disabled = true;
  loadDemoButton.textContent = "Loading...";
  fetch("api/load-demo", { method: "POST" })
    .then((response) => (response.ok ? response.json() : Promise.reject(response)))
    .then(() => loadAllLayers())
    .catch(() => window.alert("ENDERETA: failed to load demo data -- check the add-on log."))
    .finally(() => {
      loadDemoButton.disabled = false;
      loadDemoButton.textContent = "Load demo data";
    });
});

const clearDemoButton = document.getElementById("clear-demo");
clearDemoButton.addEventListener("click", () => clearDemoLayers());

// Satellite built-up layer: a separate trigger and separate Leaflet
// layers from streets/buildings above -- coarse density polygons and
// raw imagery, not numbered addresses, so they must never be visually
// confused with them (distinct colour/style, on-screen disclaimer,
// and their own layer-control group).
let satelliteMaskLayer = null;
let trueColourOverlay = null;
let ndbiOverlay = null;
let ndviOverlay = null;
let satelliteLayerControl = null;

const loadSatelliteButton = document.getElementById("load-satellite");
const satellitePanel = document.getElementById("satellite-panel");
const satelliteNote = document.getElementById("satellite-note");
const ndbiSlider = document.getElementById("ndbi-threshold");
const ndbiValue = document.getElementById("ndbi-threshold-value");
const ndviSlider = document.getElementById("ndvi-threshold");
const ndviValue = document.getElementById("ndvi-threshold-value");
const recomputeButton = document.getElementById("recompute");

ndbiSlider.addEventListener("input", () => {
  ndbiValue.textContent = parseFloat(ndbiSlider.value).toFixed(2);
});
ndviSlider.addEventListener("input", () => {
  ndviValue.textContent = parseFloat(ndviSlider.value).toFixed(2);
});

function fetchSatellite(ndbiThreshold, ndviThreshold) {
  return fetch("api/load-satellite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ndbi_threshold: ndbiThreshold, ndvi_threshold: ndviThreshold }),
  })
    .then((response) => (response.ok ? response.json() : Promise.reject(response)))
    .then((result) => {
      const imgBounds = L.latLngBounds(
        [result.bounds_wgs84[1], result.bounds_wgs84[0]], // south, west
        [result.bounds_wgs84[3], result.bounds_wgs84[2]] // north, east
      );

      [satelliteMaskLayer, trueColourOverlay, ndbiOverlay, ndviOverlay].forEach((layer) => {
        if (layer) map.removeLayer(layer);
      });
      if (satelliteLayerControl) map.removeControl(satelliteLayerControl);

      return fetch(`data/built_up.geojson?t=${Date.now()}`)
        .then((response) => response.json())
        .then((data) => {
          satelliteMaskLayer = L.geoJSON(data, {
            style: { color: "#b3541e", weight: 1, fillOpacity: 0.35 },
          });
          trueColourOverlay = L.imageOverlay(`data/true_colour.png?t=${Date.now()}`, imgBounds);
          ndbiOverlay = L.imageOverlay(`data/ndbi.png?t=${Date.now()}`, imgBounds, { opacity: 0.85 });
          ndviOverlay = L.imageOverlay(`data/ndvi.png?t=${Date.now()}`, imgBounds, { opacity: 0.85 });

          // True colour on by default, underneath the mask -- seeing the
          // real photo is the whole point of this panel, it shouldn't
          // require hunting for a checkbox first. NDBI/NDVI stay opt-in
          // (showing all three heatmaps at once is visual noise); order
          // matters here, Leaflet stacks later .addTo() calls on top.
          trueColourOverlay.addTo(map);
          satelliteMaskLayer.addTo(map);
          map.fitBounds(imgBounds, { padding: [24, 24] });
          satelliteLayerControl = L.control
            .layers(
              null,
              {
                "True colour (Sentinel-2)": trueColourOverlay,
                "Built-up mask": satelliteMaskLayer,
                "NDBI heatmap": ndbiOverlay,
                "NDVI heatmap": ndviOverlay,
              },
              { collapsed: false }
            )
            .addTo(map);

          satellitePanel.hidden = false;
          satelliteNote.textContent =
            `Scene ${result.scene_id} (${result.scene_datetime}, ` +
            `${result.cloud_cover.toFixed(1)}% cloud). Coarse built-up signal ` +
            "(~10m/pixel) -- NOT individual building footprints. Toggle layers " +
            "below to compare the mask against the real imagery. See DOCS.md.";
        });
    });
}

loadSatelliteButton.addEventListener("click", () => {
  loadSatelliteButton.disabled = true;
  loadSatelliteButton.textContent = "Fetching Sentinel-2...";
  fetchSatellite(parseFloat(ndbiSlider.value), parseFloat(ndviSlider.value))
    .catch(() =>
      window.alert("ENDERETA: failed to load the satellite layer -- check the add-on log.")
    )
    .finally(() => {
      loadSatelliteButton.disabled = false;
      loadSatelliteButton.textContent = "Load satellite layer (Sentinel-2)";
    });
});

recomputeButton.addEventListener("click", () => {
  recomputeButton.disabled = true;
  recomputeButton.textContent = "Recomputing...";
  fetchSatellite(parseFloat(ndbiSlider.value), parseFloat(ndviSlider.value))
    .catch(() => window.alert("ENDERETA: recompute failed -- check the add-on log."))
    .finally(() => {
      recomputeButton.disabled = false;
      recomputeButton.textContent = "Recompute with these thresholds";
    });
});

// Estimated addressing: real OSM streets + building points sampled
// from the Sentinel-2 built-up mask, run through the same numbering
// pipeline as the demo fixture. Kept as its own layer set (distinct
// colour, own note) -- these building locations are ESTIMATES (a grid
// sample, not a real footprint), never to be visually confused with
// the synthetic demo layer or the raw satellite mask.
const estimateLayers = [];
const estimateButton = document.getElementById("estimate-addresses");
const estimateNote = document.getElementById("estimate-note");

function loadEstimateLayer(url, style) {
  return fetch(`${url}?t=${Date.now()}`)
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data) return;
      const layer = L.geoJSON(data, style).addTo(map);
      estimateLayers.push(layer);
      const layerBounds = layer.getBounds();
      if (layerBounds.isValid()) map.fitBounds(layerBounds, { padding: [24, 24] });
    });
}

estimateButton.addEventListener("click", () => {
  estimateButton.disabled = true;
  estimateButton.textContent = "Estimating (Sentinel-2 + OSM)...";
  estimateLayers.splice(0).forEach((layer) => map.removeLayer(layer));

  fetch("api/estimate-addresses", { method: "POST" })
    .then((response) => (response.ok ? response.json() : Promise.reject(response)))
    .then((result) =>
      Promise.all([
        loadEstimateLayer("data/estimated_streets.geojson", {
          style: { color: "#6a4c93", weight: 1.5, dashArray: [4, 3] },
        }),
        loadEstimateLayer("data/estimated_buildings.geojson", {
          pointToLayer: (feature, latlng) =>
            L.circleMarker(latlng, { radius: 4, color: "#6a4c93", fillOpacity: 0.9 }),
          onEachFeature: (feature, layer) => {
            const props = feature.properties || {};
            if (props.display_address) layer.bindPopup(props.display_address);
          },
        }),
      ]).then(() => {
        estimateNote.hidden = false;
        estimateNote.textContent =
          `${result.count} addresses assigned to ESTIMATED building points ` +
          `(grid-sampled inside the Sentinel-2 built-up mask, scene ${result.scene_id}) ` +
          `against ${result.n_streets} real OSM streets. Not real building footprints -- see DOCS.md.`;
      })
    )
    .catch(() =>
      window.alert("ENDERETA: failed to estimate addresses -- check the add-on log.")
    )
    .finally(() => {
      estimateButton.disabled = false;
      estimateButton.textContent = "Assign addresses (estimated)";
    });
});
