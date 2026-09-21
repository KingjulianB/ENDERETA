// No raster basemap tiles: OpenStreetMap's tile usage policy explicitly
// forbids using tile.openstreetmap.org from a packaged/distributed app
// without prior OSMF sysadmin approval (osm.wiki/Blocked) -- confirmed
// blocked with a 403 on a real run. Rather than swap in another
// third-party tile host whose current terms aren't verified either,
// this POC viewer just renders the data on a neutral background and
// auto-fits the map to whatever loads. A compliant basemap (a licensed
// provider, or self-hosted tiles) is a deployment-time decision, not a
// wiring concern for this fixture-level demo.
// Huambo city centre -- verified 2026-09-21 (Wikipedia/geodatos.net,
// cross-checked against a real Sentinel-2 scene), not an approximation.
const map = L.map("map", { attributionControl: false }).setView(
  [-12.77611, 15.73917],
  14
);

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
