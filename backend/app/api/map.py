"""Static national baseline-hazard map data.

Deliberately dumb/cacheable: this data changes only when
scripts/build_county_map_data.py is re-run (a new WRC vintage or Census
boundary release), never per-request. Kept fully separate from /api/score
so the static baseline layer and the live weather-informed score can never
be blended into one number.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

MAP_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "map" / "us_counties.geojson"

DISCLAIMER = "Baseline hazard only; check local conditions for a personalized preparedness indicator."

LEGEND = [
    {"label": "Low", "color": "#2e7d32", "range": [0.0, 0.25]},
    {"label": "Moderate", "color": "#b58900", "range": [0.25, 0.50]},
    {"label": "High", "color": "#d2691e", "range": [0.50, 0.75]},
    {"label": "Extreme", "color": "#c1272d", "range": [0.75, 1.0]},
    {"label": "No data", "color": "#9e9e9e", "range": None},
]


@router.get("/map/counties")
def get_counties():
    if not MAP_DATA_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="County map data is not available on this server. Run scripts/build_county_map_data.py.",
        )
    with MAP_DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/map/meta")
def get_map_meta():
    source_props = {}
    if MAP_DATA_PATH.exists():
        with MAP_DATA_PATH.open(encoding="utf-8") as f:
            source_props = json.load(f).get("properties", {})

    return {
        "boundaries_source": source_props.get(
            "boundaries_source", "US Census Bureau Cartographic Boundary Files"
        ),
        "hazard_source": source_props.get(
            "hazard_source", "USDA Forest Service Wildfire Risk to Communities"
        ),
        "hazard_vintage": source_props.get("hazard_vintage", "unknown"),
        "resolution": "county",
        "legend": LEGEND,
        "disclaimer": DISCLAIMER,
    }
