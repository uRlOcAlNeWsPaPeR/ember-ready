"""Static national seismic-hazard grid data for the Earthquake Risk map.

Deliberately dumb/cacheable, same pattern as app/api/map.py's fire hazard
endpoint: this data changes only when scripts/fetch_seismic_hazard.py is
re-run, never per-request. Live earthquake markers are fetched directly
by the frontend from USGS's own feed (fully open CORS), so there's no
backend involvement needed for those at all.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

GRID_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seismic_grid.geojson"

DISCLAIMER = "Long-term shaking hazard — not a prediction."

LEGEND = [
    {"label": "Low", "color": "#2e7d32"},
    {"label": "Moderate", "color": "#b58900"},
    {"label": "High", "color": "#d2691e"},
    {"label": "Very High", "color": "#c1272d"},
]


@router.get("/seismic/grid")
def get_seismic_grid():
    if not GRID_DATA_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Seismic hazard grid is not available on this server. Run scripts/fetch_seismic_hazard.py.",
        )
    with GRID_DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/seismic/meta")
def get_seismic_meta():
    source_props = {}
    if GRID_DATA_PATH.exists():
        with GRID_DATA_PATH.open(encoding="utf-8") as f:
            source_props = json.load(f).get("properties", {})

    return {
        "source": source_props.get(
            "source", "USGS 2023 National Seismic Hazard Model"
        ),
        "metric": source_props.get("metric", ""),
        "legend": LEGEND,
        "disclaimer": DISCLAIMER,
    }
