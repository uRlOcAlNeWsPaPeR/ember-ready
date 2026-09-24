const API_BASE = window.EMBERREADY_API_BASE || "";

// USGS's official real-time feeds — fetched directly from the browser
// (USGS serves these with open CORS, verified), never proxied through our
// own backend. See https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
const FEEDS = {
  day: "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
  week: "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson",
  month: "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson",
};

const TERRAIN_TILE_URL = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png";
const TERRAIN_ATTRIBUTION =
  'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)';

const CONUS_BOUNDS = L.latLngBounds([24.0, -126.0], [50.0, -66.0]);
const AK_BOUNDS = L.latLngBounds([54.0, -170.0], [71.5, -129.0]);
const HI_BOUNDS = L.latLngBounds([18.5, -160.5], [22.5, -154.5]);
const INSET_STATE_BOUNDS = { AK: AK_BOUNDS, HI: HI_BOUNDS };

const map = L.map("eq-map", {
  scrollWheelZoom: true,
  maxBounds: CONUS_BOUNDS.pad(0.15),
  maxBoundsViscosity: 1.0,
  minZoom: 3,
  zoomControl: false,
}).fitBounds(CONUS_BOUNDS);
L.control.zoom({ position: "topright" }).addTo(map);
L.tileLayer(TERRAIN_TILE_URL, { attribution: TERRAIN_ATTRIBUTION, maxZoom: 17 }).addTo(map);

function createInsetMap(containerId, bounds) {
  const insetMap = L.map(containerId, {
    zoomControl: false,
    attributionControl: false,
    scrollWheelZoom: false,
    dragging: false,
    doubleClickZoom: false,
    maxBounds: bounds.pad(0.25),
    maxBoundsViscosity: 1.0,
  }).fitBounds(bounds);
  L.tileLayer(TERRAIN_TILE_URL, { maxZoom: 12 }).addTo(insetMap);
  return insetMap;
}

const insetMaps = {
  AK: createInsetMap("eq-inset-ak", AK_BOUNDS),
  HI: createInsetMap("eq-inset-hi", HI_BOUNDS),
};

// The seismic hazard overlay and the quake markers load independently and
// asynchronously — whichever fetch finishes second paints on top, which
// could silently put a hazard grid cell over a marker and steal its click.
// A dedicated, higher-stacked pane keeps markers clickable regardless of
// which layer happens to load first.
for (const m of [map, insetMaps.AK, insetMaps.HI]) {
  m.createPane("quakePane");
  m.getPane("quakePane").style.zIndex = 450;
}

let quakeMarkers = { main: [], AK: [], HI: [] };
let currentPeriod = "day";

document.getElementById("eq-reset-view-btn").addEventListener("click", () => {
  const animate = !EmberReadyEffects.reduceMotionPreferred();
  map.flyToBounds(CONUS_BOUNDS, { animate });
});

document.getElementById("eq-info-btn").addEventListener("click", () => {
  EmberReadyModal.open("Sources & Safety", document.querySelector('[data-modal-home="sources-safety"]'));
});

// --- Seismic hazard overlay (USGS 2023 National Seismic Hazard Model, ---
// --- sampled via their live design-value service — see backend for how) ---

function styleForCell(feature) {
  return {
    fillColor: feature.properties.color,
    fillOpacity: 0.45,
    color: feature.properties.color,
    weight: 0,
  };
}

function buildLegend(legend, disclaimer, methodology) {
  const el = document.getElementById("eq-legend-strip");
  el.innerHTML =
    "<strong>Seismic hazard</strong>" +
    legend
      .map(
        (entry) =>
          `<div class="legend-row"><span class="legend-swatch" style="background:${entry.color}"></span>${entry.label}</div>`
      )
      .join("") +
    `<div class="legend-vintage">${disclaimer}</div>` +
    `<div class="legend-vintage">Source: USGS</div>`;

  const methodologyEl = document.getElementById("sources-methodology");
  if (methodologyEl) methodologyEl.textContent = methodology;
}

function styleForStateOutline() {
  return {
    fill: false,
    color: "#4a4a4a",
    weight: 1,
    opacity: 0.65,
  };
}

async function initStateBoundaries() {
  try {
    const states = await fetch(`${API_BASE}/api/map/states`).then((r) => r.json());
    const akFeatures = states.features.filter((f) => f.properties.stusps === "AK");
    const hiFeatures = states.features.filter((f) => f.properties.stusps === "HI");
    const mainFeatures = states.features.filter(
      (f) => f.properties.stusps !== "AK" && f.properties.stusps !== "HI" && f.properties.stusps !== "PR"
    );
    L.geoJSON(mainFeatures, { style: styleForStateOutline }).addTo(map);
    L.geoJSON(akFeatures, { style: styleForStateOutline }).addTo(insetMaps.AK);
    L.geoJSON(hiFeatures, { style: styleForStateOutline }).addTo(insetMaps.HI);
  } catch (err) {
    // State outlines are a visual aid, not critical data — fail quietly.
  }
}

async function initSeismicOverlay() {
  try {
    const [meta, grid] = await Promise.all([
      fetch(`${API_BASE}/api/seismic/meta`).then((r) => r.json()),
      fetch(`${API_BASE}/api/seismic/grid`).then((r) => r.json()),
    ]);
    buildLegend(meta.legend, meta.disclaimer, meta.metric);

    const mainFeatures = grid.features.filter((f) => {
      const [lon, lat] = f.geometry.coordinates[0][0];
      return !INSET_STATE_BOUNDS.AK.contains([lat, lon]) && !INSET_STATE_BOUNDS.HI.contains([lat, lon]);
    });
    const akFeatures = grid.features.filter((f) => {
      const [lon, lat] = f.geometry.coordinates[0][0];
      return INSET_STATE_BOUNDS.AK.contains([lat, lon]);
    });
    const hiFeatures = grid.features.filter((f) => {
      const [lon, lat] = f.geometry.coordinates[0][0];
      return INSET_STATE_BOUNDS.HI.contains([lat, lon]);
    });

    L.geoJSON(mainFeatures, { style: styleForCell }).addTo(map);
    L.geoJSON(akFeatures, { style: styleForCell }).addTo(insetMaps.AK);
    L.geoJSON(hiFeatures, { style: styleForCell }).addTo(insetMaps.HI);

    await initStateBoundaries();
  } catch (err) {
    document.getElementById("eq-legend-strip").innerHTML =
      '<p class="fine-print">Seismic hazard overlay could not be loaded right now.</p>';
  }
}

// --- Live earthquake markers ---------------------------------------------

function radiusForMagnitude(mag) {
  if (mag === null || mag === undefined) return 5;
  return Math.min(28, Math.max(4, 3 + mag * 3));
}

// The USGS feed is global — EmberReady is a US-only tool (see its
// disclaimers elsewhere), and rendering thousands of off-screen worldwide
// markers would also just slow the map down for no benefit. A small FIXED
// degree buffer (not bounds.pad(), which scales with the region's own
// size — 30% of CONUS's ~60° width swallows half the Pacific) keeps quakes
// just offshore, common near US coastlines, visible.
function padBounds(bounds, degrees) {
  return L.latLngBounds(
    [bounds.getSouth() - degrees, bounds.getWest() - degrees],
    [bounds.getNorth() + degrees, bounds.getEast() + degrees]
  );
}
const US_REGION_BOUNDS = [padBounds(CONUS_BOUNDS, 5), padBounds(AK_BOUNDS, 5), padBounds(HI_BOUNDS, 3)];

function isWithinUSRegion(lat, lon) {
  return US_REGION_BOUNDS.some((bounds) => bounds.contains([lat, lon]));
}

function targetMapKeyFor(lat, lon) {
  if (INSET_STATE_BOUNDS.AK.contains([lat, lon])) return "AK";
  if (INSET_STATE_BOUNDS.HI.contains([lat, lon])) return "HI";
  return "main";
}

function mapInstanceFor(key) {
  return key === "main" ? map : insetMaps[key];
}

function clearQuakeMarkers() {
  for (const key of Object.keys(quakeMarkers)) {
    quakeMarkers[key].forEach((m) => mapInstanceFor(key).removeLayer(m));
    quakeMarkers[key] = [];
  }
}

function formatDepth(coords) {
  const depthKm = coords[2];
  if (depthKm === null || depthKm === undefined) return "Unknown";
  return `${depthKm.toFixed(1)} km`;
}

function showQuakeDetail(props, coords) {
  const when = new Date(props.time);
  const content = document.getElementById("quake-detail-content");
  content.innerHTML = `
    <div class="risk-summary">
      <div class="rs-score" style="font-size:2.4rem;">M ${props.mag !== null ? props.mag.toFixed(1) : "?"}</div>
      <div class="rs-location">${props.place || "Location unavailable"}</div>
    </div>
    <div class="rs-components">
      <div class="rs-component">
        <div class="rc-label">Date &amp; Time</div>
        <div class="rc-value" style="font-size:1rem;">${when.toLocaleString()}</div>
      </div>
      <div class="rs-component">
        <div class="rc-label">Depth</div>
        <div class="rc-value" style="font-size:1rem;">${formatDepth(coords)}</div>
      </div>
    </div>
    <a class="btn btn-block" href="${props.url}" target="_blank" rel="noopener" style="margin-top:16px;">Open Official USGS Event Page</a>
  `;
  EmberReadyModal.open("Earthquake Details", content);
}

function renderQuakes(geojson) {
  clearQuakeMarkers();

  const usFeatures = geojson.features.filter((feature) => {
    const [lon, lat] = feature.geometry.coordinates;
    return isWithinUSRegion(lat, lon);
  });

  usFeatures.forEach((feature) => {
    const [lon, lat] = feature.geometry.coordinates;
    const key = targetMapKeyFor(lat, lon);
    const targetMap = mapInstanceFor(key);
    const marker = L.circleMarker([lat, lon], {
      pane: "quakePane",
      radius: radiusForMagnitude(feature.properties.mag),
      fillColor: "#6d28d9",
      fillOpacity: 0.65,
      color: "#ffffff",
      weight: 1.5,
    }).addTo(targetMap);
    marker.bindTooltip(feature.properties.title || feature.properties.place, { sticky: true });
    marker.on("click", () => showQuakeDetail(feature.properties, feature.geometry.coordinates));
    quakeMarkers[key].push(marker);
  });

  const generated = geojson.metadata && geojson.metadata.generated;
  const countText = `${usFeatures.length} US-region earthquake${usFeatures.length === 1 ? "" : "s"}`;
  const updatedText = generated ? `Last updated: ${new Date(generated).toLocaleString()}` : "";
  document.getElementById("eq-last-updated").textContent = `${countText} · ${updatedText}`;
}

async function loadQuakes(period) {
  document.getElementById("eq-last-updated").textContent = "Fetching recent earthquakes…";
  try {
    const resp = await fetch(FEEDS[period]);
    if (!resp.ok) throw new Error("feed request failed");
    const geojson = await resp.json();
    renderQuakes(geojson);
  } catch (err) {
    document.getElementById("eq-last-updated").textContent =
      "Could not load live earthquake data from USGS right now.";
  }
}

document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.period === currentPeriod) return;
    document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentPeriod = btn.dataset.period;
    loadQuakes(currentPeriod);
  });
});

window.addEventListener("resize", () => {
  map.invalidateSize();
  insetMaps.AK.invalidateSize();
  insetMaps.HI.invalidateSize();
});

initSeismicOverlay();
loadQuakes(currentPeriod);
