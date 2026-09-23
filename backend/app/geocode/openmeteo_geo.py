"""Open-Meteo Geocoding client — free, no API key. Used as a fallback for
ZIP codes and city/place names that the Census address geocoder can't match
(it expects a full street address).
"""
from __future__ import annotations

import httpx

from app.schemas import Location, Resolution, SearchType

BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT = 10.0


class OpenMeteoGeocodeError(Exception):
    pass


def _search(query: str, count: int, client: httpx.Client) -> list[dict]:
    resp = client.get(
        BASE_URL,
        params={"name": query, "count": count, "language": "en", "format": "json", "countryCode": "US"},
    )
    resp.raise_for_status()
    return resp.json().get("results") or []


def _label_for(result: dict) -> str:
    parts = [result.get("name"), result.get("admin1"), result.get("country_code")]
    return ", ".join(p for p in parts if p)


def geocode_place(query: str, client: httpx.Client | None = None) -> Location:
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        results = _search(query, count=1, client=client)
    finally:
        if owns_client:
            client.close()

    if not results:
        raise OpenMeteoGeocodeError(f"No Open-Meteo geocoding match for: {query!r}")

    top = results[0]
    return Location(
        latitude=top["latitude"],
        longitude=top["longitude"],
        matched_address=_label_for(top),
        resolution=Resolution.NEIGHBORHOOD,
        source="Open-Meteo Geocoding API (place-name centroid)",
        search_type=SearchType.PLACE,
    )


def search_suggestions(query: str, count: int = 5, client: httpx.Client | None = None) -> list[dict]:
    """Lightweight typeahead suggestions (city/town/ZIP name matches) for the
    frontend's autocomplete dropdown. Not used for scoring itself — a
    selected suggestion's lat/lon is passed straight to /api/score.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        results = _search(query, count=count, client=client)
    finally:
        if owns_client:
            client.close()

    return [
        {"label": _label_for(r), "latitude": r["latitude"], "longitude": r["longitude"]}
        for r in results
    ]
