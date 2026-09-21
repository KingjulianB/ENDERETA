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

const bounds = L.latLngBounds([]);
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

// Satellite built-up layer: a separate trigger and a separate Leaflet
// layer from streets/buildings above -- it's a different kind of data
// (a coarse density polygon, not a numbered address) and must never be
// visually confused with them, hence the distinct colour/style and the
// on-screen disclaimer.
let satelliteLayer = null;
const loadSatelliteButton = document.getElementById("load-satellite");
const satelliteNote = document.getElementById("satellite-note");

loadSatelliteButton.addEventListener("click", () => {
  loadSatelliteButton.disabled = true;
  loadSatelliteButton.textContent = "Fetching Sentinel-2...";
  fetch("api/load-satellite", { method: "POST" })
    .then((response) => (response.ok ? response.json() : Promise.reject(response)))
    .then((result) => {
      if (satelliteLayer) map.removeLayer(satelliteLayer);
      return fetch(`data/built_up.geojson?t=${Date.now()}`)
        .then((response) => response.json())
        .then((data) => {
          satelliteLayer = L.geoJSON(data, {
            style: { color: "#b3541e", weight: 1, fillOpacity: 0.35 },
          }).addTo(map);
          satelliteNote.hidden = false;
          satelliteNote.textContent =
            `Coarse built-up signal from Sentinel-2 scene ${result.scene_id} ` +
            `(${result.scene_datetime}, ${result.cloud_cover.toFixed(1)}% cloud) -- ` +
            "NOT individual building footprints. See DOCS.md.";
        });
    })
    .catch(() =>
      window.alert("ENDERETA: failed to load the satellite layer -- check the add-on log.")
    )
    .finally(() => {
      loadSatelliteButton.disabled = false;
      loadSatelliteButton.textContent = "Load satellite layer (Sentinel-2)";
    });
});
