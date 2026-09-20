// No raster basemap tiles: OpenStreetMap's tile usage policy explicitly
// forbids using tile.openstreetmap.org from a packaged/distributed app
// without prior OSMF sysadmin approval (osm.wiki/Blocked) -- confirmed
// blocked with a 403 on a real run. Rather than swap in another
// third-party tile host whose current terms aren't verified either,
// this POC viewer just renders the data on a neutral background and
// auto-fits the map to whatever loads. A compliant basemap (a licensed
// provider, or self-hosted tiles) is a deployment-time decision, not a
// wiring concern for this fixture-level demo.
const map = L.map("map", { attributionControl: false }).setView(
  [-12.7756, 15.7392],
  14
);

const bounds = L.latLngBounds([]);

function loadLayer(url, style) {
  fetch(url)
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data) return;
      const layer = L.geoJSON(data, style).addTo(map);
      const layerBounds = layer.getBounds();
      if (layerBounds.isValid()) {
        bounds.extend(layerBounds);
        map.fitBounds(bounds, { padding: [24, 24] });
      }
    })
    .catch(() => console.warn(`ENDERETA: no data yet at ${url}`));
}

loadLayer("data/streets.geojson", { style: { color: "#2a6f97", weight: 2 } });
loadLayer("data/buildings.geojson", {
  pointToLayer: (feature, latlng) =>
    L.circleMarker(latlng, { radius: 5, color: "#d1495b", fillOpacity: 0.9 }),
  onEachFeature: (feature, layer) => {
    const props = feature.properties || {};
    if (props.display_address) layer.bindPopup(props.display_address);
  },
});
