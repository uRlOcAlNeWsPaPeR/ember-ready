// Small shared fetch helpers for the real, no-fabrication data sources
// EmberReady layers on top of the core risk score: EPA-style air quality
// (via Open-Meteo) and official NWS active alerts. Both fail silently
// (return null / []) on network error — they're contextual enrichment, not
// required for the core risk score to render.
const EmberReadyAwarenessData = (() => {
  const API_BASE = window.EMBERREADY_API_BASE || "";

  async function fetchAirQuality(lat, lon) {
    try {
      const resp = await fetch(`${API_BASE}/api/air-quality?lat=${lat}&lon=${lon}`);
      if (!resp.ok) return null;
      return await resp.json();
    } catch (err) {
      return null;
    }
  }

  async function fetchAlerts(lat, lon) {
    try {
      const resp = await fetch(`${API_BASE}/api/alerts?lat=${lat}&lon=${lon}`);
      if (!resp.ok) return [];
      const data = await resp.json();
      return data.alerts || [];
    } catch (err) {
      return [];
    }
  }

  async function fetchFireAlert(lat, lon) {
    const alerts = await fetchAlerts(lat, lon);
    return alerts.find((a) => a.is_fire_related) || null;
  }

  function windDirectionLabel(deg) {
    if (deg === null || deg === undefined) return "";
    const dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
    return dirs[Math.round(deg / 22.5) % 16];
  }

  return { fetchAirQuality, fetchAlerts, fetchFireAlert, windDirectionLabel };
})();

window.EmberReadyAwarenessData = EmberReadyAwarenessData;
