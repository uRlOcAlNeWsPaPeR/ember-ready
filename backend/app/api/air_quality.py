from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.weather.air_quality import AirQualityFetchError, get_current_air_quality

router = APIRouter()


class AirQualityResponse(BaseModel):
    us_aqi: int
    category: str
    pm2_5: float
    pm10: float
    observed_at: str
    source: str
    note: str = "Contextual only — not a wildfire risk input. See EPA AQI categories."


@router.get("/air-quality", response_model=AirQualityResponse)
def get_air_quality(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> AirQualityResponse:
    try:
        with httpx.Client(timeout=10.0) as client:
            reading = get_current_air_quality(lat, lon, client=client)
    except AirQualityFetchError as exc:
        raise HTTPException(status_code=502, detail=f"Air quality data unavailable: {exc}") from exc

    return AirQualityResponse(
        us_aqi=reading.us_aqi,
        category=reading.category,
        pm2_5=reading.pm2_5,
        pm10=reading.pm10,
        observed_at=reading.observed_at.isoformat(),
        source=reading.source,
    )
