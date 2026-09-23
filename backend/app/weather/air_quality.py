"""Open-Meteo Air Quality API client — free, no API key.

Deliberately kept OUT of the wildfire risk scoring model (weights.json):
air quality is useful context for a household deciding whether to be
outside clearing brush today, but it is not a wildfire hazard input, and
folding it into the score would blur what the score actually measures.
Exposed as its own lightweight endpoint instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEOUT = 10.0
SOURCE = "Open-Meteo Air Quality API (US AQI)"

# Standard EPA US AQI categories — not something this app defines.
AQI_CATEGORIES = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
    (10_000, "Hazardous"),
]


class AirQualityFetchError(Exception):
    pass


@dataclass
class AirQualityReading:
    us_aqi: int
    category: str
    pm2_5: float
    pm10: float
    observed_at: datetime
    source: str = SOURCE


def _category_for(aqi: int) -> str:
    for threshold, label in AQI_CATEGORIES:
        if aqi <= threshold:
            return label
    return AQI_CATEGORIES[-1][1]


def get_current_air_quality(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> AirQualityReading:
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = client.get(
            BASE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "us_aqi,pm2_5,pm10",
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise AirQualityFetchError(f"Open-Meteo Air Quality request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    try:
        current = data["current"]
        aqi = int(current["us_aqi"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AirQualityFetchError(f"Unexpected Open-Meteo Air Quality response: {data}") from exc

    try:
        observed_at = datetime.fromisoformat(current["time"])
    except (KeyError, ValueError):
        observed_at = datetime.now(timezone.utc)

    return AirQualityReading(
        us_aqi=aqi,
        category=_category_for(aqi),
        pm2_5=current.get("pm2_5"),
        pm10=current.get("pm10"),
        observed_at=observed_at,
    )
