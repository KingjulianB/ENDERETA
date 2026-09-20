// Approximate Huambo city centre -- replace with the real POC district
// centroid once the AOI polygon is supplied.
const map = L.map("map").setView([-12.7756, 15.7392], 14);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

function loadLayer(url, style) {
  fetch(url)
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (data) L.geoJSON(data, style).addTo(map);
    })
    .catch(() => console.warn(`ENDERETA: no data yet at ${url}`));
}

loadLayer("data/streets.geojson", { style: { color: "#2a6f97", weight: 2 } });
loadLayer("data/buildings.geojson", {
  pointToLayer: (feature, latlng) =>
    L.circleMarker(latlng, { radius: 3, color: "#d1495b" }),
  onEachFeature: (feature, layer) => {
    const props = feature.properties || {};
    if (props.display_address) layer.bindPopup(props.display_address);
  },
});
