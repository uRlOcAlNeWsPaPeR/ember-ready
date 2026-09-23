"""USGS 3DEP Elevation Point Query Service (EPQS) client.

EPQS returns elevation at a single point only — it does not return slope.
We estimate local slope by sampling four neighboring points (~90m offsets,
matching the ~30m-90m native resolution of 3DEP data in most of the US) and
taking the steepest of the two finite-difference gradients (N-S, E-W). This
is a neighborhood-scale estimate, not a parcel-exact slope value.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.schemas import Resolution

BASE_URL = "https://epqs.nationalmap.gov/v1/json"
TIMEOUT = 10.0

# ~90 meters in degrees latitude; longitude offset is adjusted for latitude.
OFFSET_METERS = 90.0
METERS_PER_DEGREE_LAT = 111_320.0

SLOPE_SOURCE = "USGS 3DEP Elevation Point Query Service (4-point local gradient estimate)"
SLOPE_RESOLUTION = Resolution.NEIGHBORHOOD


class ElevationFetchError(Exception):
    pass


@dataclass
class SlopeReading:
    slope_pct: float
    center_elevation_m: float
    observed_at: datetime
    source: str = SLOPE_SOURCE
    resolution: Resolution = SLOPE_RESOLUTION


def get_elevation_m(latitude: float, longitude: float, client: httpx.Client) -> float:
    resp = client.get(
        BASE_URL,
        params={"x": longitude, "y": latitude, "units": "Meters", "wkid": 4326, "includeDate": False},
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        return float(data["value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ElevationFetchError(f"Unexpected EPQS response: {data}") from exc


def get_slope(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> SlopeReading:
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        dlat = OFFSET_METERS / METERS_PER_DEGREE_LAT
        meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude))
        dlon = OFFSET_METERS / meters_per_degree_lon

        try:
            center = get_elevation_m(latitude, longitude, client)
            north = get_elevation_m(latitude + dlat, longitude, client)
            south = get_elevation_m(latitude - dlat, longitude, client)
            east = get_elevation_m(latitude, longitude + dlon, client)
            west = get_elevation_m(latitude, longitude - dlon, client)
        except httpx.HTTPError as exc:
            raise ElevationFetchError(f"USGS EPQS request failed: {exc}") from exc

        ns_slope_pct = abs(north - south) / (2 * OFFSET_METERS) * 100
        ew_slope_pct = abs(east - west) / (2 * OFFSET_METERS) * 100
        slope_pct = max(ns_slope_pct, ew_slope_pct)

        return SlopeReading(
            slope_pct=slope_pct,
            center_elevation_m=center,
            observed_at=datetime.now(timezone.utc),
        )
    finally:
        if owns_client:
            client.close()
