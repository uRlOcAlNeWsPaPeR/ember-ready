"""NOAA/National Weather Service active alerts — free, no API key.

Surfaces real official alerts for a point (Red Flag Warnings, Fire Weather
Watches, and any other active NWS alert for the area). This is the "active
official alerts" input EmberReady can honestly show: it is exactly the same
public feed NWS publishes to weather.gov, not a simulated or inferred alert.

EmberReady does not decide what counts as an emergency — it only surfaces
what NWS has actually issued, verbatim, with a link back to the official
alert.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

BASE_URL = "https://api.weather.gov/alerts/active"
TIMEOUT = 10.0
USER_AGENT = "EmberReady (educational wildfire-preparedness app)"

FIRE_RELATED_EVENTS = {
    "red flag warning",
    "fire weather watch",
    "extreme fire danger",
}


class AlertsFetchError(Exception):
    pass


@dataclass
class AlertReading:
    event: str
    headline: str
    severity: str
    urgency: str
    area_desc: str
    effective: datetime | None
    expires: datetime | None
    url: str
    is_fire_related: bool


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_active_alerts(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> list[AlertReading]:
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    try:
        resp = client.get(BASE_URL, params={"point": f"{latitude},{longitude}"})
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise AlertsFetchError(f"NWS alerts request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    readings = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        event = props.get("event", "")
        readings.append(
            AlertReading(
                event=event,
                headline=props.get("headline", event),
                severity=props.get("severity", "Unknown"),
                urgency=props.get("urgency", "Unknown"),
                area_desc=props.get("areaDesc", ""),
                effective=_parse_dt(props.get("effective")),
                expires=_parse_dt(props.get("expires")),
                url=props.get("@id", "https://www.weather.gov/"),
                is_fire_related=event.strip().lower() in FIRE_RELATED_EVENTS,
            )
        )
    return readings
