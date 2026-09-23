# EmberReady 🔥

A hyperlocal wildfire preparedness web app for the United States, built for
the Congressional App Challenge. Enter a US street address or ZIP code to
get **two explicitly separated** 0–100 indicators — long-term baseline
wildfire exposure and today's fire weather — combined into a transparent
preparedness indicator, plus a data-quality panel that never hides a
missing data source behind an invented number. Answer a few household
questions for a personalized preparedness checklist. A national map lets
you explore county-level baseline hazard across the whole country, or
click/search to zoom into the same live, personalized result.

**EmberReady is a student hackathon project — not an emergency alert
system, not an official fire-risk determination, and not affiliated with
any government agency. It covers the United States only.** For active
incidents, evacuation orders, and real-time updates, always consult local
fire authorities, Watch Duty, and other official emergency sources.

## Problem

Most wildfire-risk information is either broad (a statewide "fire season"
warning) or reactive (an active-incident map once a fire has already
started). There's little that combines *today's* weather conditions with a
location's longer-term baseline hazard to help a household decide "should I
be doing my defensible-space chores this weekend?" — and turn that into a
concrete, personalized to-do list. EmberReady does both, and is explicit
about the precision limits of the data behind it.

## Safety scope

- **Educational/preparedness tool only.** Not a substitute for official
  fire-risk assessments, insurance underwriting, or emergency alerts.
- **United States only** for this MVP — addresses/ZIPs outside the US are
  not supported.
- **Never incident-specific.** The personalized checklist gives generic,
  area-independent preparedness guidance; it never claims to know about a
  specific active fire or evacuation order.
- **Resolution is always labeled.** Every factor in the score breakdown
  states whether it's point-level, neighborhood-scale, a ~1–11km weather
  grid cell, a 30m raster cell, or county-scale — so the UI never implies
  more precision than the underlying data supports.
- A persistent disclaimer banner and footer point users to local fire
  authorities and Watch Duty for anything real-time.
- **The national map is a baseline hazard map, not a real-time or
  evacuation map.** It shows the same county-level, modeled burn-probability
  data described above — colored by category, never blended with live
  weather. Every popup repeats "baseline hazard only; check local
  conditions for a personalized preparedness indicator."

## Data sources and limitations

| Factor | Source | Resolution | Notes |
|---|---|---|---|
| Full street address → lat/lon | US Census Bureau Geocoder | Address-range interpolated | Free, no key, public domain. Primary path whenever the query isn't a bare ZIP. |
| **ZIP code → lat/lon** | **US Census Bureau ZCTA Gazetteer (2024)** — `backend/data/zcta_centroids.csv`, 33,791 ZCTAs | **ZIP centroid (explicitly approximate)** | A bare 5-digit ZIP is detected and resolved against Census's own official ZCTA centroid file — not a third-party geocoder's fuzzy place-name guess. Still only approximates a whole ZCTA area (often many square miles), so it is always labeled `location_precision: zip_centroid` and shown with an explicit "NOT property-specific" warning — never presented as address-level. |
| City/town name → lat/lon | Open-Meteo Geocoding API | Place centroid | Fallback only when Census can't match a full address (e.g. a landmark or city name with no street number). |
| Current weather | Open-Meteo Forecast API | ~1–11km model grid | Temp, RH, wind, gusts, live, no key. |
| Days since meaningful rain | Open-Meteo Forecast API (`past_days`) | Same grid | **Documented threshold: ≥2.5mm (0.1in) daily precipitation counts as "meaningful," capped at 21 days.** (An earlier version fetched 14 days of history but normalized against a 30-day range — silently capping this factor at half its intended weight even in a real drought. The lookback window and normalization range are now the same number, read from one config file, so they can't drift apart again — see `weights.json`.) |
| Terrain slope | USGS 3DEP EPQS | Neighborhood (4-point ~90m gradient) | EPQS gives elevation only; slope is derived locally, not an exact parcel value. |
| Vegetation/fuel proxy | LANDFIRE FBFM40 (live WMS `GetFeatureInfo`) | 30m grid | Real per-pixel live query — no bulk download needed. The 0-1 hazard score is **EmberReady's own simplified proxy**, grouped from the standard Scott & Burgan 40 fuel model catalog — not an official LANDFIRE hazard rating or a fire-behavior model output. |
| Baseline wildfire exposure | USDA Forest Service Wildfire Risk to Communities | **County-scale** | A **modeled** long-term burn-probability percentile (FSim simulation), not observed fire history. No live point API exists, so a small pre-extracted CSV (`backend/data/wrc_counties.csv`, 3,144 counties) ships with the app — see `backend/scripts/fetch_static_layers.py`. **If a county has no WRC data (confirmed cases: DC and 78 territory counties), this factor is excluded from the score and clearly flagged — never silently replaced with a default value.** |
| National map county boundaries | US Census Bureau Cartographic Boundary Files (2023, county, 20m generalization) | **County-scale** | Public domain, no key. Converted once to a static GeoJSON (`backend/data/map/us_counties.geojson`) joined with the same WRC burn-probability data above — see `backend/scripts/build_county_map_data.py`. Never fetched live. |
| Plain-language "Ask AI to explain this" text (risk score panel) | Google Gemini API (`backend/app/api/ai_explain.py`, `/api/explain`) | N/A — text only | **Disclosed AI usage.** Optional, opt-in, and strictly bounded: the prompt hands the model only the factor values already computed and shown on screen, and instructs it never to add a fact, statistic, or safety instruction beyond what's given. It restates the existing score in plain sentences — it does not compute, alter, or independently determine any part of the score itself. The deterministic explainer sentence above it needs no AI and is always shown regardless of whether this feature is configured. |
| "Ask AI to summarize my plan" text (Plan screen, both hazards) | Google Gemini API (`backend/app/api/ai_explain.py`, `/api/plan-summary`) | N/A — text only | **Disclosed AI usage.** Same bounded pattern as above: the prompt hands the model only the user's own real checklist/review items and their done/not-done state (all stored locally — see "Safety scope"), and instructs it never to invent a new preparedness step. It restates and encourages progress on the existing checklist — it never adds a step the checklist itself doesn't already have. Resets whenever the underlying checklist changes, so it can never show stale advice next to fresh progress. |

**Known MVP limitations** (documented rather than hidden):
- Weather is a model-grid value bilinear-interpolated to your point, not a
  hyperlocal sensor reading.
- The baseline exposure factor is county-wide — two houses on opposite
  sides of a county line get the same value even though real risk varies
  block-to-block. A LANDFIRE/WRC raster-grid layer at finer resolution is a
  documented stretch goal, not yet integrated.
- The fuel-hazard proxy score is a hand-assigned simplification for
  explainability, not a calibrated fire-behavior output.
- Active-fire detection (e.g. NASA FIRMS) is intentionally **not**
  integrated into the score — mixing "is there a fire right now" with
  "how fire-conducive are conditions" would blur an important distinction
  and risk implying real-time incident awareness the app doesn't have.

## Scoring methodology

`backend/app/scoring/weights.json` is the **single source of truth** for
every weight, normalization range, and the rationale behind it — not a
Python constant. `backend/app/scoring/config.py` loads and validates it
(fails loudly at import time if the weights don't actually sum to 100).
`weighted_model.py` implements a **fully transparent, hand-weighted
formula — explicitly not machine learning.**

**Two risk concepts are kept structurally separate, and both are always
returned and displayed — never averaged away into one hidden number:**

- **`baseline_wildfire_exposure`** (65% of the combined weight) — long-term
  regional hazard: burn probability (35), fuel/vegetation (20), slope (10).
- **`current_fire_weather`** (35% of the combined weight) — today's
  conditions: wind gusts (9), wind speed (6), relative humidity (6),
  temperature (4), days since meaningful rain (10).
- **`preparedness_indicator`** — the transparent combination
  (`baseline*0.65 + weather*0.35`), explicitly labeled an educational
  preparedness indicator, not an official risk prediction.

Baseline is weighted well above weather specifically so a single calm day
cannot make a genuinely hazardous location look safe — and because both
component scores are always shown side by side, a high baseline is never
hidden even when today's weather pulls the combined number down. Gusts are
weighted above sustained wind speed (embers/spotting, the dominant spread
mechanism, are gust-driven) and humidity above temperature (the more direct
fuel-moisture indicator in standard fire-weather indices) — full rationale
for every weight is written directly in `weights.json`.

Label thresholds: Low (0–25), Moderate (26–50), High (51–75), Extreme
(76–100), applied independently to each of the three scores above.

**Missing data is never defaulted.** If a source fails or has no data for a
location (weather timeout, LANDFIRE outage, a county with no WRC data), that
factor is excluded — its weight is dropped from the affected component's
denominator so the component stays on a comparable 0–100 scale computed
only from what's actually known — and a `data_quality` object on every
response reports `confidence` (High/Medium/Low), which factors were
unavailable and why, and how many points were excluded. The UI shows this
prominently, never buries it.

**Every factor is individually explainable** ("Why this result?" in the
UI): raw value, normalized value, weight, point contribution, source,
geographic resolution, and dataset vintage/timestamp — whether available or
excluded.

**Future ML path:** `backend/app/scoring/model_interface.py` defines an
abstract `RiskModel.score()` interface. A future `SklearnRiskModel` could
implement the same interface — trained on historical incidence data with a
**time-aware train/test split**, evaluated against this weighted model as a
baseline, held out on unseen data, and explained via permutation importance
or SHAP (avoiding leakage from post-fire indicators) — and be swapped in
without changing the API or frontend.

## API

- `GET /api/score?query=<address-or-zip>` or `?lat=&lon=` — returns
  `location` (with `search_type`, `location_precision`, and a human-readable
  `location_precision_label`), the three separated scores
  (`baseline_wildfire_exposure`, `current_fire_weather`,
  `preparedness_indicator`), the full `factors` breakdown, a `data_quality`
  object (confidence, which factors were unavailable and why, whether a
  geocoding fallback was used), and a `safety_notice` string with the exact
  required disclaimer text.
- `GET /api/geocode/suggest?q=` — typeahead suggestions for the search box.
- `GET /api/map/counties` / `GET /api/map/meta` — the static national
  choropleth data and its legend/attribution (cached, never computed
  per-request).

## Architecture

```
ember-ready/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app; also serves frontend/ as static files
│   │   ├── api/                    # score.py, checklist.py, map.py, geocode.py (routes + Pydantic response models)
│   │   ├── geocode/                # census.py, zcta.py, openmeteo_geo.py, resolver.py (3-path: ZIP/address/place)
│   │   ├── weather/                # openmeteo.py
│   │   ├── baseline/                # elevation_slope.py, fuel_vegetation.py, fire_history.py
│   │   ├── scoring/
│   │   │   ├── weights.json         # single source of truth for every weight + written rationale
│   │   │   ├── config.py            # loads + validates weights.json
│   │   │   ├── model_interface.py
│   │   │   └── weighted_model.py    # two-track scorer with graceful per-factor degradation
│   │   ├── checklist/                # rules.py (rule-based, not ML)
│   │   ├── cache/                   # db.py (SQLite cache for score responses)
│   │   ├── schemas.py               # shared dataclasses used across modules
│   │   └── pipeline.py              # fetches each factor independently; failures never block the others
│   ├── data/
│   │   ├── wrc_counties.csv         # committed county burn-probability CSV
│   │   ├── zcta_centroids.csv       # committed Census ZCTA gazetteer (33,791 ZIP centroids)
│   │   ├── map/us_counties.geojson  # committed national map data (see build_county_map_data.py)
│   │   └── cache.sqlite3            # gitignored, created at runtime
│   ├── scripts/
│   │   ├── fetch_static_layers.py       # regenerates wrc_counties.csv from the WRC workbook
│   │   ├── fetch_zip_centroids.py       # regenerates zcta_centroids.csv from the Census gazetteer
│   │   └── build_county_map_data.py     # regenerates us_counties.geojson (Census shapefile + wrc_counties.csv)
│   ├── tests/
│   │   ├── fixtures/locations.json  # 22-location validation fixture (see Testing below)
│   │   └── ...                      # pytest: mocked unit tests + opt-in live integration tests
│   ├── requirements.txt / requirements-dev.txt
│   └── run.sh                       # one-command local setup + run
├── frontend/                        # wildfire awareness + preparedness — mobile-first, 2 screens
│   ├── index.html / map.js          # Map (landing screen): national hazard map, search, "Locate Me",
│   │                                 # popups for Risk Details / Wind & Air Quality / Active Alerts.
│   │                                 # Restores the last-checked location on return visits.
│   ├── plan.html / plan.js          # Plan: Before / During / After a Wildfire, checklists in popups
│   ├── shared/app-state.js          # localStorage state + Before/During/After progress model
│   ├── shared/score-panel.js        # risk summary UI (simple view + "See the details")
│   ├── shared/awareness-data.js     # air-quality + NWS-alerts fetch helpers
│   ├── shared/modal.js              # shared popup component used by Map and Plan
│   ├── shared/nav.js                # bottom navigation (Map / Plan)
│   ├── shared/effects.js            # Reduce Motion + High Contrast (via a small settings popup),
│   │                                 # ember→blue spark animation
│   ├── shared/address-autocomplete.js
│   └── style.css                    # design system (light theme + High Contrast mode)
├── Procfile / render.yaml           # deployment
└── README.md
```

**Stack:** Python + FastAPI backend, plain HTML/CSS/JS frontend (no
framework needed for this scope), SQLite for response caching, no auth. The
frontend is served by the same FastAPI process as the API, so local dev and
deployment are both a single process/service.

## Setup

```bash
git clone <this repo>
cd ember-ready/backend
./run.sh
```

`run.sh` creates a virtualenv, installs dependencies, and starts the app at
`http://localhost:8000`. That's the one command.

**Optional: AI features.** Two buttons — "✨ Ask AI to explain this" in the
risk score panel, and "✨ Ask AI to summarize my plan" on the Plan screen —
call [Google Gemini](https://aistudio.google.com/apikey) (free tier) to turn
data the app already computed or tracked (score factors, checklist progress)
into a plain-language paragraph. Both are entirely optional — everything
else in the app works with zero API keys. To enable them, set an
environment variable before starting the backend:

```bash
export GEMINI_API_KEY=your-key-here
```

Without it, both buttons quietly report the AI text as unavailable; every
deterministic element they sit next to (the explainer sentence, the
checklist itself) needs no AI and is always shown regardless.

To regenerate the committed county-level baseline data or map data
(optional — both are already checked in):

```bash
cd backend
source venv/bin/activate
python -m scripts.fetch_static_layers        # backend/data/wrc_counties.csv
python -m scripts.fetch_zip_centroids        # backend/data/zcta_centroids.csv
python -m scripts.build_county_map_data      # backend/data/map/us_counties.geojson
```

## Testing

```bash
cd backend
source venv/bin/activate
python -m pytest -q                 # fast, fully mocked (respx) — safe for CI
RUN_LIVE_TESTS=1 python -m pytest -q tests/test_pipeline_live.py   # hits the real 5 external APIs
```

The mocked suite covers normal and edge cases for every module (the 3-path
geocode resolver, weather parsing, slope math, fuel-code lookup, county
lookup misses, scorer bounds/monotonicity, checklist rule conditions, API
error-code mapping, the committed map GeoJSON's structural integrity, and
the map API endpoints). The live suite is skipped by default so grading/CI
never depends on network availability, but exists to catch real upstream
breakage.

**`tests/test_validation_fixture.py`** is a data-driven suite over
**`tests/fixtures/locations.json`**, 22 diverse US locations: high-exposure
western, low-exposure eastern/urban, full-address and ZIP-only searches,
wet/calm vs. hot/dry/windy weather scenarios, and missing-data/fallback
cases (a real WRC gap at DC, a failed reverse-geocode, a LANDFIRE timeout, a
total weather outage). For every entry it asserts: the correct geocoding
path was used, no factor is ever silently defaulted when its source data is
absent, each component score's contributions sum to exactly what's
reported, labels match the documented thresholds, confidence reacts
correctly to missing data, and ZIP results are always labeled approximate.
**This validates software behavior and scoring consistency — it does not
prove and is not offered as proof of real-world wildfire risk for any of
the 22 locations**, which is stated directly in the fixture file.

## Deployment (Render or Railway)

Both `render.yaml` and `Procfile` are at the repo root and point to the
same command:

```
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Render:** connect the repo; Render will detect `render.yaml` and deploy
automatically (build: `pip install -r backend/requirements.txt`).

**Railway:** connect the repo; Railway auto-detects the `Procfile`. No
environment variables are required for the core app — the only optional one
is `GEMINI_API_KEY` (see Setup above), which just enables the AI explanation
button; every other feature uses no API keys anywhere in the live request path.

## Demo script

EmberReady is a wildfire *awareness and preparedness* tool — it does not
call for help, message contacts, or track anyone's safety status. It has
three jobs: show whether conditions are elevated nearby, show a plain-language
risk percentage, and give clear before/during/after guidance.

1. Open the app on a phone-sized window. It lands directly on **Map** — a
   full-screen national hazard choropleth, a search bar, and one "Locate Me"
   button (real browser geolocation). Nothing is fabricated for "near you"
   until you actually search or share your location.
2. Type **"Chic"** in the search bar and note the address/city/ZIP dropdown
   updating live as you type (debounced, real suggestions from the backend).
   Pick **"Chico, California, US"**.
3. The info sheet slides up with a compact summary — status word (No Current
   Fire Concern / Prepare / High Risk / Active Fire Nearby), a risk
   percentage, and the matched area — plus three tappable rows: **Risk
   Details**, **Wind & Air Quality**, and **Active Official Alerts**. Nothing
   is dumped on screen at once; each row opens its full detail in a popup.
4. Tap **Risk Details**: status, percentage, and a one-sentence explanation
   built live from the real contributing factors (wind, dryness, regional
   hazard) — never a canned sentence per status tier. Expand **"See the
   details"** inside that same popup for the separated area-hazard/weather
   scores, data confidence, and full factor tables.
5. Search **"20001"** (Washington, DC) — a real gap in the USDA dataset —
   and reopen Risk Details to show the burn-probability factor rendered as
   excluded with its real failure reason, confidence dropped to Medium.
6. Tap **Wind & Air Quality**: real wind speed/direction and air quality
   (Open-Meteo), each labeled with source and time. Tap **Active Official
   Alerts**: real NWS alerts for that exact point, each linking out to the
   official alert page — an empty list is labeled "no active alert right
   now," never as "safe."
7. Switch to the **Plan** tab, then back to **Map** — the location you
   searched is still there: same pin, same summary, freshly refetched rather
   than replayed from a stale cache.
8. On **Plan**: three plans, in order — Before / During / After a Wildfire —
   each a compact row with a live progress badge (e.g. "3/24"). Tap **Before**
   to open its checklist popup, fill out the household form (try "rent" +
   "pets"), and note the "Included because: renter / pet_owner" tags plus
   the three collapsible categories (evacuation plan, go-bag, home
   protection), each with its own count.
9. Check off a few items — watch the ember spark fly to the plan's node on
   the page behind the popup, and the connecting path glow blue as each plan
   completes. Open **During** and **After**: general official guidance
   (evacuate early, avoid smoke, check air quality, document damage),
   checkable locally just to track what's been read — never framed as
   EmberReady's own instructions.
10. Tap the small gear icon (top-right, present on both screens) for
    **Reduce Motion** and **High Contrast** — the only settings in the app,
    since there's no household-management or account screen to hang them on.
11. Close by reiterating the framing: educational awareness and preparedness
    tool, US-only, never an emergency communication system — it can't call
    for help, message anyone, or track a safety status — missing data always
    shown as missing, never a substitute for official alerts or evacuation
    guidance.
