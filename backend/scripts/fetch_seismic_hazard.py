"""Data prep: build a national seismic-hazard grid for the Earthquake Risk
map overlay, sampled from USGS's live ASCE 7-22 design-value web service
(https://earthquake.usgs.gov/ws/designmaps/asce7-22.json), which computes
its values directly from the 2023 National Seismic Hazard Model (NSHM).

There is no ready-made national GeoJSON/raster of NSHM hazard categories —
USGS distributes the raw model as large (40-85MB) national shapefiles
requiring GIS raster tooling to process. Instead, this script samples the
same underlying model at a grid of points via USGS's own live web service
(the same one structural engineers use to look up code-required design
values for a single site) and buckets the result into four public-facing
categories. This is real NSHM-derived data at every point — coarser than
the full-resolution model, but not fabricated or interpolated by us.

The metric used is Ss: the Mapped Risk-Targeted Maximum Considered
Earthquake (MCEr) spectral response acceleration at a 0.2-second period,
for reference Site Class B/C boundary rock, at the model's standard 2%
probability of exceedance in 50 years. This is the same parameter USGS's
own national hazard maps display.

Run with: python -m scripts.fetch_seismic_hazard
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

DESIGN_MAPS_URL = "https://earthquake.usgs.gov/ws/designmaps/asce7-22.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "seismic_grid.geojson"

# Same regional bounds used by the fire map (frontend/map.js), so both
# hazard layers line up on the same national/Alaska/Hawaii view.
CONUS_BOUNDS = {"lat": (24.0, 50.0), "lon": (-125.0, -66.0), "step": 2.0}
AK_BOUNDS = {"lat": (54.0, 71.0), "lon": (-170.0, -129.0), "step": 2.0}
HI_BOUNDS = {"lat": (18.5, 22.5), "lon": (-160.5, -154.5), "step": 1.0}

CONCURRENCY = 8
REQUEST_TIMEOUT = 15.0

# Category thresholds on Ss (g). Not an official USGS categorical scheme —
# USGS publishes continuous hazard values, not a 4-bucket label — these are
# EmberReady's own round, disclosed breakpoints for a simple public map.
CATEGORIES = [
    (0.25, "Low", "#2e7d32"),
    (0.50, "Moderate", "#b58900"),
    (1.00, "High", "#d2691e"),
    (float("inf"), "Very High", "#c1272d"),
]


def category_for(ss: float) -> tuple[str, str]:
    for threshold, label, color in CATEGORIES:
        if ss < threshold:
            return label, color
    return CATEGORIES[-1][1], CATEGORIES[-1][2]


def grid_points(bounds: dict) -> list[tuple[float, float]]:
    lat_lo, lat_hi = bounds["lat"]
    lon_lo, lon_hi = bounds["lon"]
    step = bounds["step"]
    points = []
    lat = lat_lo
    while lat <= lat_hi:
        lon = lon_lo
        while lon <= lon_hi:
            points.append((round(lat, 2), round(lon, 2)))
            lon += step
        lat += step
    return points


async def fetch_ss(client: httpx.AsyncClient, lat: float, lon: float) -> float | None:
    try:
        resp = await client.get(
            DESIGN_MAPS_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "riskCategory": "II",
                "siteClass": "BC",
                "title": "EmberReady grid sample",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        ss = data["response"]["data"].get("ss")
        return float(ss) if ss is not None else None
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        # Ocean points, or points outside the model's coverage, error out —
        # that's expected and means "no data" here, not a bug to fix.
        return None


async def fetch_all(points: list[tuple[float, float]]) -> list[dict]:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results: list[dict | None] = [None] * len(points)

    async def worker(i: int, lat: float, lon: float, client: httpx.AsyncClient):
        async with semaphore:
            ss = await fetch_ss(client, lat, lon)
        if ss is not None:
            label, color = category_for(ss)
            results[i] = {"lat": lat, "lon": lon, "ss": ss, "category": label, "color": color}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        tasks = [worker(i, lat, lon, client) for i, (lat, lon) in enumerate(points)]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(points)} points checked...")

    return [r for r in results if r is not None]


def cell_polygon(lat: float, lon: float, step: float) -> dict:
    half = step / 2
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - half, lat - half],
                [lon + half, lat - half],
                [lon + half, lat + half],
                [lon - half, lat + half],
                [lon - half, lat - half],
            ]
        ],
    }


async def main() -> None:
    all_features = []
    for region_name, bounds in [("CONUS", CONUS_BOUNDS), ("Alaska", AK_BOUNDS), ("Hawaii", HI_BOUNDS)]:
        points = grid_points(bounds)
        print(f"Sampling {len(points)} {region_name} grid points...")
        results = await fetch_all(points)
        print(f"  {len(results)}/{len(points)} had NSHM data.")
        for r in results:
            all_features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "ss": r["ss"],
                        "category": r["category"],
                        "color": r["color"],
                    },
                    "geometry": cell_polygon(r["lat"], r["lon"], bounds["step"]),
                }
            )

    feature_collection = {
        "type": "FeatureCollection",
        "properties": {
            "source": "USGS 2023 National Seismic Hazard Model, sampled via the ASCE 7-22 design-value web service",
            "metric": "Ss — Mapped Risk-Targeted MCEr spectral response acceleration at 0.2s, Site Class B/C, 2% probability of exceedance in 50 years",
            "disclaimer": "Long-term shaking hazard — not a prediction.",
        },
        "features": all_features,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, separators=(",", ":"))

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\nWrote {len(all_features)} grid cells to {OUTPUT_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
