// Reusable risk-summary panel: builds its own DOM into a container element
// and exposes a `render(data)` method. Used by the "Know Your Risk" chapter
// on the Plan screen and by the Map screen's info sheet, so this UI is only
// ever maintained once.
//
// The primary view is deliberately calm and simple — one status word, one
// plain-language sentence, nothing else competing for attention. All of the
// underlying transparency work (separated baseline/weather scores, data
// confidence, unavailable-factor disclosure, full factor tables) still
// exists and is never hidden — it just lives behind a "See the details"
// disclosure instead of being shown by default, per the "one primary
// action per screen" rule.
const EmberReadyScorePanel = (() => {
  // Maps the underlying Low/Moderate/High/Extreme scoring labels to the
  // plain-language public vocabulary used everywhere else in the app.
  const STATUS_MAP = {
    Low: { word: "No Current Fire Concern", pillClass: "pill-safe" },
    Moderate: { word: "Prepare", pillClass: "pill-prepare" },
    High: { word: "High Risk", pillClass: "pill-high" },
    Extreme: { word: "Active Fire Nearby", pillClass: "pill-emergency" },
  };

  function statusFor(label) {
    return STATUS_MAP[label] || { word: "Unknown", pillClass: "pill-unknown" };
  }

  function factorByName(data, name) {
    return (data.factors || []).find((f) => f.name === name);
  }

  // Builds a short, honest explanation from the same real factors the score
  // is computed from — never a canned sentence per status tier. `extras`
  // can carry air-quality and active-alert context fetched separately (see
  // shared/awareness-data.js), since those aren't part of the /api/score
  // response itself.
  function buildExplanation(data, extras) {
    extras = extras || {};
    const drivers = [];

    const gusts = factorByName(data, "wind_gusts");
    const wind = factorByName(data, "wind_speed");
    if (gusts && gusts.available && gusts.normalized_value > 0.5) drivers.push("strong wind gusts");
    else if (wind && wind.available && wind.normalized_value > 0.5) drivers.push("elevated wind speed");

    const dryness = factorByName(data, "days_since_rain");
    const humidity = factorByName(data, "relative_humidity");
    if (dryness && dryness.available && dryness.normalized_value > 0.5) drivers.push("an extended dry spell");
    else if (humidity && humidity.available && humidity.normalized_value > 0.5) drivers.push("low humidity");

    const burn = factorByName(data, "burn_probability");
    if (burn && burn.available && burn.normalized_value > 0.6) drivers.push("high regional fire hazard");

    if (extras.airQuality && extras.airQuality.us_aqi >= 101) {
      drivers.push(`${extras.airQuality.category.toLowerCase()} air quality`);
    }
    if (extras.fireAlert) {
      drivers.push(`an active ${extras.fireAlert.event} for your area`);
    }

    let sentence;
    if (drivers.length === 0) {
      sentence = "Conditions are calm right now — normal wind, typical humidity, and no active fire-weather alerts.";
    } else if (drivers.length === 1) {
      sentence = `Driven by ${drivers[0]}.`;
    } else {
      const last = drivers[drivers.length - 1];
      sentence = `Driven by ${drivers.slice(0, -1).join(", ")} and ${last}.`;
    }

    if (data.preparedness_indicator.label === "Extreme") {
      sentence += " This reflects fire-weather conditions, not a confirmed fire detection.";
    }
    return sentence;
  }

  function create(container) {
    container.innerHTML = `
      <div class="risk-summary">
        <span class="pill" data-role="status-pill">--</span>
        <div class="rs-score" data-role="rs-score">--</div>
        <div class="rs-location" data-role="rs-location"></div>
        <p class="rs-explainer" data-role="rs-explainer"></p>
        <div class="rs-precision hidden" data-role="rs-precision"></div>

        <div class="rs-components">
          <div class="rs-component">
            <div class="rc-label">Area hazard</div>
            <div class="rc-value" data-role="baseline-number">--</div>
          </div>
          <div class="rs-component">
            <div class="rc-label">Today's weather</div>
            <div class="rc-value" data-role="weather-number">--</div>
          </div>
        </div>

        <p class="safety-line" data-role="safety-notice"></p>

        <details class="rs-details">
          <summary>See the details</summary>

          <p>
            EmberReady uses a transparent, hand-weighted formula — not a black-box model.
            Long-term area hazard (burn probability, vegetation, terrain) is kept structurally
            separate from today's fire weather (wind, humidity, temperature, dry spell), so a
            calm-weather day can never silently hide a high baseline hazard. This is
            educational information, not an official prediction.
          </p>

          <div class="rs-components">
            <div class="rs-component">
              <div class="rc-label">Data confidence</div>
              <div class="rc-value" data-role="confidence-badge">--</div>
            </div>
            <div class="rs-component">
              <div class="rc-label">Factors available</div>
              <div class="rc-value" data-role="dq-availability">--</div>
            </div>
          </div>

          <div data-role="unavailable-list"></div>
          <p class="fine-print hidden" data-role="fallback-note"></p>

          <h4>Area hazard factors</h4>
          <table class="rs-factor-table">
            <thead><tr><th>Factor</th><th>Value</th><th>Contribution</th></tr></thead>
            <tbody data-role="baseline-factors-body"></tbody>
          </table>

          <h4>Today's weather factors</h4>
          <table class="rs-factor-table">
            <thead><tr><th>Factor</th><th>Value</th><th>Contribution</th></tr></thead>
            <tbody data-role="weather-factors-body"></tbody>
          </table>
        </details>
      </div>
    `;

    const els = {};
    container.querySelectorAll("[data-role]").forEach((el) => {
      els[el.dataset.role] = el;
    });

    function renderFactorRow(factor) {
      const tr = document.createElement("tr");
      if (!factor.available) tr.className = "rs-unavailable";

      const nameTd = document.createElement("td");
      nameTd.textContent = factor.name.replace(/_/g, " ");
      if (!factor.available) {
        const small = document.createElement("div");
        small.className = "fine-print";
        small.textContent = `Unavailable: ${factor.unavailable_reason}`;
        nameTd.appendChild(small);
      }

      const valueTd = document.createElement("td");
      valueTd.textContent = factor.available ? `${factor.raw_value.toFixed(2)} ${factor.raw_unit}` : "—";

      const contribTd = document.createElement("td");
      contribTd.textContent = factor.available
        ? `${factor.contribution_points.toFixed(1)} / ${factor.weight_points.toFixed(0)} pts`
        : `excluded (${factor.weight_points.toFixed(0)} pts)`;

      tr.append(nameTd, valueTd, contribTd);
      return tr;
    }

    let lastData = null;

    function render(data, extras) {
      lastData = data;
      const status = statusFor(data.preparedness_indicator.label);
      els["status-pill"].textContent = status.word;
      els["status-pill"].className = `pill ${status.pillClass}`;
      els["rs-score"].textContent =
        data.preparedness_indicator.score === null || data.preparedness_indicator.score === undefined
          ? "N/A"
          : Math.round(data.preparedness_indicator.score);
      els["rs-location"].textContent = data.location.matched_address;
      els["rs-explainer"].textContent = buildExplanation(data, extras);

      const precision = els["rs-precision"];
      if (data.search_type === "zip" || data.search_type === "place") {
        precision.textContent = data.location.location_precision_label;
        precision.classList.remove("hidden");
      } else {
        precision.classList.add("hidden");
      }

      const baseline = data.baseline_wildfire_exposure;
      const weather = data.current_fire_weather;
      els["baseline-number"].textContent =
        baseline.score === null || baseline.score === undefined ? "N/A" : `${baseline.label}`;
      els["weather-number"].textContent =
        weather.score === null || weather.score === undefined ? "N/A" : `${weather.label}`;

      els["safety-notice"].textContent = data.safety_notice;

      const dq = data.data_quality;
      els["confidence-badge"].textContent = dq.confidence;
      els["dq-availability"].textContent = `${dq.factors_available} of ${dq.factors_total}`;

      const unavailableList = els["unavailable-list"];
      unavailableList.innerHTML = "";
      if (dq.unavailable_factors.length > 0) {
        const heading = document.createElement("p");
        heading.className = "fine-print";
        heading.textContent = "Unavailable data (excluded from the score, not guessed):";
        unavailableList.appendChild(heading);
        const ul = document.createElement("ul");
        for (const uf of dq.unavailable_factors) {
          const li = document.createElement("li");
          li.textContent = `${uf.factor.replace(/_/g, " ")} (${uf.weight_excluded} pts): ${uf.reason}`;
          ul.appendChild(li);
        }
        unavailableList.appendChild(ul);
      }

      const fallbackNote = els["fallback-note"];
      if (dq.fallback_used) {
        fallbackNote.textContent = `ℹ ${dq.fallback_detail}`;
        fallbackNote.classList.remove("hidden");
      } else {
        fallbackNote.classList.add("hidden");
      }

      const baselineBody = els["baseline-factors-body"];
      const weatherBody = els["weather-factors-body"];
      baselineBody.innerHTML = "";
      weatherBody.innerHTML = "";
      for (const factor of data.factors) {
        const row = renderFactorRow(factor);
        if (factor.category === "baseline_wildfire_exposure") baselineBody.appendChild(row);
        else weatherBody.appendChild(row);
      }
    }

    function updateExplanation(extras) {
      if (!lastData) return;
      els["rs-explainer"].textContent = buildExplanation(lastData, extras);
    }

    return { render, updateExplanation, container };
  }

  return { create, statusFor, buildExplanation };
})();

window.EmberReadyScorePanel = EmberReadyScorePanel;
