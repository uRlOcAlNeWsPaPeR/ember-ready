const API_BASE = window.EMBERREADY_API_BASE || "";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTRIBUTION = "&copy; OpenStreetMap contributors";

// The main map is locked to the contiguous US only — Alaska and Hawaii get
// their own small inset maps, in the classic cartographic corner-box
// convention. Territories (PR, GU, VI, MP, AS) are excluded for this MVP.
const CONUS_BOUNDS = L.latLngBounds([24.0, -126.0], [50.0, -66.0]);
const AK_BOUNDS = L.latLngBounds([54.0, -170.0], [71.5, -129.0]);
const HI_BOUNDS = L.latLngBounds([18.5, -160.5], [22.5, -154.5]);
const INSET_STATE_CODES = { AK: AK_BOUNDS, HI: HI_BOUNDS };
const EXCLUDED_FROM_MAIN = new Set(["AK", "HI", "PR", "GU", "VI", "MP", "AS"]);

const map = L.map("map", {
  scrollWheelZoom: true,
  maxBounds: CONUS_BOUNDS.pad(0.15),
  maxBoundsViscosity: 1.0,
  // Low enough that the whole contiguous US still fits on a phone-width
  // viewport — a higher floor clamps fitBounds and crops the west coast.
  minZoom: 3,
  zoomControl: false,
}).fitBounds(CONUS_BOUNDS);
L.control.zoom({ position: "topright" }).addTo(map);
L.tileLayer(OSM_TILE_URL, { attribution: OSM_ATTRIBUTION, maxZoom: 18 }).addTo(map);

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
  L.tileLayer(OSM_TILE_URL, { maxZoom: 10 }).addTo(insetMap);
  return insetMap;
}

const insetMaps = {
  AK: createInsetMap("inset-ak", AK_BOUNDS),
  HI: createInsetMap("inset-hi", HI_BOUNDS),
};

let markers = {};
let legendByLabel = {};
let lastClickedLatLng = null;

const scorePanel = EmberReadyScorePanel.create(document.getElementById("score-panel-mount"));
attachAddressAutocomplete(document.getElementById("map-query"));

function targetMapKeyFor(lat, lon) {
  const latlng = L.latLng(lat, lon);
  for (const [code, bounds] of Object.entries(INSET_STATE_CODES)) {
    if (bounds.contains(latlng)) return code;
  }
  return "main";
}

function mapInstanceFor(key) {
  return key === "main" ? map : insetMaps[key];
}

// Set while placeMarker() is swapping out the old marker for a new one, so
// the popupclose Leaflet fires during that cleanup doesn't also trigger
// removeAllMarkers() and fight with the marker just being added below.
let suppressPopupCloseRemoval = false;

function removeAllMarkers() {
  for (const [k, m] of Object.entries(markers)) {
    mapInstanceFor(k).removeLayer(m);
  }
  markers = {};
}

// The user is explicitly done with this place — remove its pin, close the
// info sheet, clear the search box, and forget it in state so it doesn't
// quietly reappear the next time they land on this tab (see
// restoreLastLocation()). Called from both the sheet's own "x" and the
// marker popup's "x", so either one gives a fully clean state.
function dismissPlace() {
  removeAllMarkers();
  document.getElementById("map-info-sheet").classList.remove("open");
  document.getElementById("map-query").value = "";
  EmberReadyState.update({ lastScore: null });
}

function placeMarker(lat, lon, popupText) {
  const key = targetMapKeyFor(lat, lon);
  const targetMap = mapInstanceFor(key);

  suppressPopupCloseRemoval = true;
  for (const [k, m] of Object.entries(markers)) {
    mapInstanceFor(k).removeLayer(m);
  }
  markers = {};
  suppressPopupCloseRemoval = false;

  const marker = L.marker([lat, lon]).addTo(targetMap);
  if (popupText) marker.bindPopup(popupText).openPopup();
  // Closing the marker's own popup (its "x") means the user is done with
  // this landmark — remove the pin from the map, not just its label.
  marker.on("popupclose", () => {
    if (suppressPopupCloseRemoval) return;
    dismissPlace();
  });
  markers[key] = marker;

  if (key === "main") {
    targetMap.flyTo([lat, lon], Math.max(targetMap.getZoom(), 9));
  }
}

const CATEGORY_STYLE = {
  Low: { weight: 1, dashArray: null },
  Moderate: { weight: 1, dashArray: "4,3" },
  High: { weight: 2, dashArray: null },
  Extreme: { weight: 2, dashArray: "4,3" },
  "No data": { weight: 1, dashArray: "1,4" },
};

function styleForFeature(feature) {
  const category = feature.properties.category;
  const color = (legendByLabel[category] && legendByLabel[category].color) || "#9e9e9e";
  const extra = CATEGORY_STYLE[category] || {};
  return {
    fillColor: color,
    fillOpacity: feature.properties.has_data ? 0.55 : 0.2,
    color: color,
    weight: extra.weight || 1,
    dashArray: extra.dashArray || null,
  };
}

function buildLegendStrip(legend) {
  const el = document.getElementById("map-legend-strip");
  el.innerHTML =
    "<strong>Baseline hazard</strong>" +
    legend
      .map(
        (entry) =>
          `<div class="legend-row"><span class="legend-swatch" style="background:${entry.color}"></span>${entry.label}</div>`
      )
      .join("");
}

function openSheet() {
  document.getElementById("map-info-sheet").classList.add("open");
}

function closeSheet() {
  document.getElementById("map-info-sheet").classList.remove("open");
}

// The user explicitly dismissing the sheet (its own "x") means they're done
// with this place — see dismissPlace(). This is distinct from closeSheet()
// used internally on a failed search, which must NOT wipe out a still-valid
// marker from an earlier successful lookup.
document.getElementById("close-sheet-btn").addEventListener("click", dismissPlace);

function showCountyInfo(properties) {
  document.getElementById("county-info-panel").classList.remove("hidden");
  document.getElementById("score-panel-section").classList.add("hidden");
  document.getElementById("county-info-name").textContent = properties.name;
  document.getElementById("county-info-category").textContent = properties.category;
  document.getElementById("county-info-percentile").textContent = properties.has_data
    ? `${Math.round(properties.bp_national_percentile * 100)}th percentile nationally`
    : "not available for this county";
  openSheet();
}

function countyPopupHtml(properties) {
  const percentileText = properties.has_data
    ? `${Math.round(properties.bp_national_percentile * 100)}th percentile nationally`
    : "No data available";
  return `<strong>${properties.name}</strong><br/>Baseline hazard: <strong>${properties.category}</strong><br/>${percentileText}`;
}

function bindCountyLayerHandlers(feature, layer) {
  layer.bindTooltip(`${feature.properties.name}: ${feature.properties.category}`, { sticky: true });
  layer.on("click", (event) => {
    lastClickedLatLng = event.latlng;
    showCountyInfo(feature.properties);
    layer.bindPopup(countyPopupHtml(feature.properties)).openPopup(event.latlng);
  });
}

function showSearchError(message) {
  const el = document.getElementById("map-search-error");
  el.textContent = message;
  el.classList.remove("hidden");
}

function clearSearchError() {
  const el = document.getElementById("map-search-error");
  el.classList.add("hidden");
  el.textContent = "";
}

async function fetchAndShowScoreForCoords(lat, lon) {
  clearSearchError();
  document.getElementById("sheet-loading").classList.remove("hidden");
  try {
    const resp = await fetch(`${API_BASE}/api/score?lat=${lat}&lon=${lon}`);
    const data = await resp.json();
    if (!resp.ok) {
      showSearchError(data.detail || "Could not fetch live conditions for this location.");
      return;
    }
    renderScoreResult(data);
  } catch (err) {
    showSearchError("Network error while fetching live conditions. Please try again.");
  } finally {
    document.getElementById("sheet-loading").classList.add("hidden");
  }
}

function renderWindAndSourceLine(data) {
  const arrow = document.getElementById("wind-arrow");
  const text = document.getElementById("wind-text");
  let windSummary;
  if (data.wind_speed_kmh === null || data.wind_speed_kmh === undefined) {
    text.textContent = "Unavailable";
    arrow.style.opacity = "0.3";
    windSummary = "Wind unavailable";
  } else {
    const dirLabel = EmberReadyAwarenessData.windDirectionLabel(data.wind_direction_deg);
    text.textContent = `${Math.round(data.wind_speed_kmh)} km/h ${dirLabel}`;
    arrow.style.opacity = "1";
    // The arrow glyph points "up" (from) by default; rotate it to point in
    // the direction wind is blowing toward (meteorological convention: the
    // reported degrees are where the wind blows FROM, so add 180°).
    arrow.style.transform = `rotate(${(data.wind_direction_deg || 0) + 180}deg)`;
    windSummary = `${Math.round(data.wind_speed_kmh)} km/h ${dirLabel}`;
  }
  document.getElementById("wind-aq-source").textContent =
    `Wind: Open-Meteo, as of ${new Date(data.generated_at).toLocaleTimeString()}.`;
  document.getElementById("wind-aq-summary").textContent = `${windSummary} · Air quality loading…`;
}

function renderAlertsPanel(alerts) {
  const panel = document.getElementById("alerts-panel");
  panel.innerHTML = "";

  if (alerts.length === 0) {
    const p = document.createElement("p");
    p.className = "fine-print";
    p.textContent = "No active NWS alerts for this area right now. This means NWS has not issued one — not that conditions are safe.";
    panel.appendChild(p);
    return;
  }

  alerts.forEach((a) => {
    const link = document.createElement("a");
    link.href = a.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.className = a.is_fire_related ? "rs-precision" : "fine-print";
    link.style.display = "block";
    link.style.marginBottom = "10px";
    link.style.textDecoration = "none";
    link.style.color = "inherit";
    const effective = a.effective ? new Date(a.effective).toLocaleString() : "unknown";
    link.innerHTML = `<strong>${a.event}</strong><br/>${a.area_desc}<br/>Effective: ${effective} — Source: NWS. Tap for the official alert →`;
    panel.appendChild(link);
  });
}

async function renderScoreResult(data) {
  document.getElementById("county-info-panel").classList.add("hidden");
  scorePanel.render(data);
  renderWindAndSourceLine(data);

  const status = EmberReadyScorePanel.statusFor(data.preparedness_indicator.label);
  const pill = document.getElementById("map-status-pill");
  pill.textContent = status.word;
  pill.className = `pill ${status.pillClass}`;
  document.getElementById("map-risk-score").textContent =
    data.preparedness_indicator.score === null || data.preparedness_indicator.score === undefined
      ? "N/A"
      : `${Math.round(data.preparedness_indicator.score)}%`;
  document.getElementById("map-location-text").textContent = data.location.matched_address;
  document.getElementById("risk-details-summary").textContent =
    `${data.baseline_wildfire_exposure.label || "N/A"} area hazard · ${data.current_fire_weather.label || "N/A"} weather`;
  document.getElementById("alerts-summary").textContent = "Checking for active alerts…";
  document.getElementById("alerts-badge").classList.add("hidden");

  document.getElementById("score-panel-section").classList.remove("hidden");
  openSheet();

  if (window.EmberReadyState) {
    EmberReadyState.update({ lastScore: data });
    EmberReadyState.markScoreViewed();
  }
  placeMarker(data.location.latitude, data.location.longitude, data.location.matched_address);

  const lat = data.location.latitude;
  const lon = data.location.longitude;
  const [airQuality, alerts] = await Promise.all([
    EmberReadyAwarenessData.fetchAirQuality(lat, lon),
    EmberReadyAwarenessData.fetchAlerts(lat, lon),
  ]);

  const aqEl = document.getElementById("aq-value");
  const windSummary = document.getElementById("wind-text").textContent;
  if (airQuality) {
    aqEl.textContent = `${airQuality.category} (AQI ${airQuality.us_aqi})`;
    document.getElementById("wind-aq-summary").textContent = `${windSummary} · ${airQuality.category} air quality`;
  } else {
    aqEl.textContent = "Unavailable";
    document.getElementById("wind-aq-summary").textContent = `${windSummary} · Air quality unavailable`;
  }
  document.getElementById("wind-aq-source").textContent =
    `Wind: Open-Meteo. Air quality: Open-Meteo, as of ${airQuality ? new Date(airQuality.observed_at).toLocaleTimeString() : "--"}.`;

  renderAlertsPanel(alerts);
  const badge = document.getElementById("alerts-badge");
  if (alerts.length > 0) {
    badge.textContent = alerts.length;
    badge.className = `tap-row-badge${alerts.some((a) => a.is_fire_related) ? " badge-attn" : ""}`;
    badge.classList.remove("hidden");
    document.getElementById("alerts-summary").textContent = `${alerts.length} active alert${alerts.length === 1 ? "" : "s"}`;
  } else {
    badge.classList.add("hidden");
    document.getElementById("alerts-summary").textContent = "No active alerts for this area";
  }

  scorePanel.updateExplanation({
    airQuality: airQuality || undefined,
    fireAlert: alerts.find((a) => a.is_fire_related) || undefined,
  });
}

document.getElementById("open-risk-details-row").addEventListener("click", () => {
  EmberReadyModal.open("Risk Details", document.querySelector('[data-modal-home="risk-details"]'));
});
document.getElementById("open-wind-aq-row").addEventListener("click", () => {
  EmberReadyModal.open("Wind & Air Quality", document.querySelector('[data-modal-home="wind-aq"]'));
});
document.getElementById("open-alerts-row").addEventListener("click", () => {
  EmberReadyModal.open("Active Official Alerts", document.querySelector('[data-modal-home="alerts"]'));
});

async function fetchAndShowScoreForQuery(query) {
  clearSearchError();
  document.getElementById("sheet-loading").classList.remove("hidden");
  openSheet();
  try {
    const resp = await fetch(`${API_BASE}/api/score?query=${encodeURIComponent(query)}`);
    const data = await resp.json();
    if (!resp.ok) {
      showSearchError(
        resp.status === 404
          ? "Could not find that address or ZIP code. EmberReady covers US addresses and ZIP codes only."
          : data.detail || "Something went wrong. Please try again."
      );
      closeSheet();
      return;
    }
    renderScoreResult(data);
  } catch (err) {
    showSearchError("Network error while searching. Please try again.");
    closeSheet();
  } finally {
    document.getElementById("sheet-loading").classList.add("hidden");
  }
}

document.getElementById("map-search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const query = document.getElementById("map-query").value.trim();
  if (!query) return;
  fetchAndShowScoreForQuery(query);
});

document.getElementById("county-info-check-score").addEventListener("click", () => {
  if (lastClickedLatLng) fetchAndShowScoreForCoords(lastClickedLatLng.lat, lastClickedLatLng.lng);
});

// --- Reset view: back to the full national map, same bounds as first load. ---
document.getElementById("reset-view-btn").addEventListener("click", () => {
  const animate = !EmberReadyEffects.reduceMotionPreferred();
  map.flyToBounds(CONUS_BOUNDS, { animate });
});

// --- Locate Me: a real browser Geolocation lookup, never a simulated
// position. The existing /api/score endpoint already accepts raw lat/lon
// directly, so no separate reverse-geocoding endpoint is needed. ---
document.getElementById("locate-me-btn").addEventListener("click", () => {
  clearSearchError();
  if (!("geolocation" in navigator)) {
    showSearchError("Your browser doesn't support location access.");
    return;
  }
  const btn = document.getElementById("locate-me-btn");
  btn.disabled = true;
  navigator.geolocation.getCurrentPosition(
    (position) => {
      btn.disabled = false;
      fetchAndShowScoreForCoords(position.coords.latitude, position.coords.longitude);
    },
    (error) => {
      btn.disabled = false;
      showSearchError(
        error.code === error.PERMISSION_DENIED
          ? "Location access was denied. You can search an address or ZIP instead."
          : "Couldn't determine your location. You can search an address or ZIP instead."
      );
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

async function initMap() {
  try {
    const metaResp = await fetch(`${API_BASE}/api/map/meta`);
    const meta = await metaResp.json();
    legendByLabel = Object.fromEntries(meta.legend.map((entry) => [entry.label, entry]));
    buildLegendStrip(meta.legend);
  } catch (err) {
    legendByLabel = {};
  }

  try {
    const resp = await fetch(`${API_BASE}/api/map/counties`);
    if (!resp.ok) throw new Error("map data request failed");
    const geojson = await resp.json();

    const mainFeatures = geojson.features.filter((f) => !EXCLUDED_FROM_MAIN.has(f.properties.state));
    const akFeatures = geojson.features.filter((f) => f.properties.state === "AK");
    const hiFeatures = geojson.features.filter((f) => f.properties.state === "HI");

    L.geoJSON(mainFeatures, { style: styleForFeature, onEachFeature: bindCountyLayerHandlers }).addTo(map);
    L.geoJSON(akFeatures, { style: styleForFeature, onEachFeature: bindCountyLayerHandlers }).addTo(insetMaps.AK);
    L.geoJSON(hiFeatures, { style: styleForFeature, onEachFeature: bindCountyLayerHandlers }).addTo(insetMaps.HI);
  } catch (err) {
    showSearchError("Could not load the national hazard map right now. You can still search an address or ZIP above.");
  }
}

window.addEventListener("resize", () => {
  map.invalidateSize();
  insetMaps.AK.invalidateSize();
  insetMaps.HI.invalidateSize();
});

// Since Map is now the app's landing screen, a location the user already
// checked shouldn't disappear the moment they visit another tab and come
// back — restore it from the last real lookup, and re-fetch fresh
// conditions for that same point rather than replaying stale numbers.
//
// An explicit page refresh is different: that's read as "start over," so it
// resets to the default full-country view instead of restoring — detected
// via the Navigation Timing API rather than a same-page vs. cross-page
// heuristic, since both look identical to a plain multi-page app otherwise.
function restoreLastLocation() {
  const data = EmberReadyState.load().lastScore;
  if (!data || !data.location) return;
  const isCoordSearch = data.search_type === "coordinates";
  document.getElementById("map-query").value = isCoordSearch ? data.location.matched_address : data.query;
  if (isCoordSearch) {
    fetchAndShowScoreForCoords(data.location.latitude, data.location.longitude);
  } else {
    fetchAndShowScoreForQuery(data.query);
  }
}

function wasPageReloaded() {
  const [nav] = performance.getEntriesByType("navigation");
  return nav ? nav.type === "reload" : false;
}

initMap();
if (!wasPageReloaded()) {
  restoreLastLocation();
}
