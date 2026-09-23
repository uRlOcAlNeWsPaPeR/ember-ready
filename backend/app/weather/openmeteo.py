"""Open-Meteo Forecast API client — free, no API key.

Provides current conditions (temperature, relative humidity, wind, gusts)
plus a recent-precipitation history used to compute "days since meaningful
rain."

The meaningful-rain threshold and lookback window are read from
scoring/weights.json (not hardcoded here) so there is exactly one
documented place that defines them. An earlier version fetched 14 days of
history but normalized the result against a 30-day range in the scorer —
silently capping this factor at half its intended weight even in a
documented drought. The lookback window here and the normalization range
in weights.json must match; `_days_since_meaningful_rain` explicitly caps
its return value at that window so the two can never drift apart again.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.schemas import Resolution
from app.scoring.config import load_weights_config

BASE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10.0

WEATHER_RESOLUTION = Resolution.GRIDDED_1_11KM
WEATHER_SOURCE = "Open-Meteo Forecast API (blended national weather models)"


class WeatherFetchError(Exception):
    pass


@dataclass
class WeatherReading:
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    wind_direction_deg: float
    days_since_meaningful_rain: float
    observed_at: datetime
    source: str = WEATHER_SOURCE
    resolution: Resolution = WEATHER_RESOLUTION


def _rain_config() -> tuple[float, int]:
    config = load_weights_config()
    return config["meaningful_rain_mm"], config["rain_lookback_days"]


def get_current_conditions(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> WeatherReading:
    meaningful_rain_mm, lookback_days = _rain_config()

    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = client.get(
            BASE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m",
                "daily": "precipitation_sum",
                "past_days": lookback_days,
                "forecast_days": 1,
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise WeatherFetchError(f"Open-Meteo request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    try:
        current = data["current"]
        daily = data["daily"]
    except KeyError as exc:
        raise WeatherFetchError(f"Unexpected Open-Meteo response shape: {data}") from exc

    days_since_rain = _days_since_meaningful_rain(
        daily["precipitation_sum"], meaningful_rain_mm, lookback_days
    )

    observed_at_str = current["time"]
    try:
        observed_at = datetime.fromisoformat(observed_at_str)
    except ValueError:
        observed_at = datetime.now(timezone.utc)

    return WeatherReading(
        temperature_c=current["temperature_2m"],
        relative_humidity_pct=current["relative_humidity_2m"],
        wind_speed_kmh=current["wind_speed_10m"],
        wind_gusts_kmh=current["wind_gusts_10m"],
        wind_direction_deg=current["wind_direction_10m"],
        days_since_meaningful_rain=days_since_rain,
        observed_at=observed_at,
    )


def _days_since_meaningful_rain(precip_mm: list[float], meaningful_rain_mm: float, lookback_days: int) -> float:
    """Walk backward from the most recent day (the last entry) and count how
    many days it's been since precipitation met `meaningful_rain_mm`.
    Explicitly capped at `lookback_days` — the actual fetched window may be
    one entry longer (today's partial forecast day included), but the
    reported value never exceeds the documented, normalized cap.
    """
    for offset, value in enumerate(reversed(precip_mm)):
        if value is not None and value >= meaningful_rain_mm:
            return float(min(offset, lookback_days))
    return float(lookback_days)
