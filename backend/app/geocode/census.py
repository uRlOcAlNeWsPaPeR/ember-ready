"""US Census Bureau Geocoder client — free, no API key, public domain.

Used as the primary resolver for full street addresses, and for reverse
lookups (lat/lon -> county FIPS) when a query was instead resolved by the
Open-Meteo place-name geocoder.
"""
from __future__ import annotations

import httpx

from app.schemas import Location, Resolution, SearchType

BASE_URL = "https://geocoding.geo.census.gov/geocoder"
TIMEOUT = 10.0


class CensusGeocodeError(Exception):
    pass


def geocode_address(address: str, client: httpx.Client | None = None) -> Location:
    """Resolve a full US street address to a point + county FIPS in one call."""
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = client.get(
            f"{BASE_URL}/geographies/onelineaddress",
            params={
                "address": address,
                "benchmark": "Public_AR_Current",
                "vintage": "Current_Current",
                "layers": "Counties",
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            client.close()

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        raise CensusGeocodeError(f"No Census match for address: {address!r}")

    match = matches[0]
    coords = match["coordinates"]
    counties = match.get("geographies", {}).get("Counties", [])
    county = counties[0] if counties else {}

    return Location(
        latitude=coords["y"],
        longitude=coords["x"],
        matched_address=match.get("matchedAddress", address),
        resolution=Resolution.POINT,
        source="US Census Bureau Geocoder (TIGER/Line, address-range interpolated)",
        search_type=SearchType.ADDRESS,
        county_fips=(county.get("STATE", "") + county.get("COUNTY", "")) or None,
        county_name=county.get("NAME"),
        state=county.get("STATE"),
    )


def reverse_geocode_county(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> dict:
    """Look up the county FIPS/name for a known lat/lon (used after place-name geocoding)."""
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = client.get(
            f"{BASE_URL}/geographies/coordinates",
            params={
                "x": longitude,
                "y": latitude,
                "benchmark": "Public_AR_Current",
                "vintage": "Current_Current",
                "layers": "Counties",
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            client.close()

    counties = data.get("result", {}).get("geographies", {}).get("Counties", [])
    if not counties:
        return {}
    county = counties[0]
    return {
        "county_fips": (county.get("STATE", "") + county.get("COUNTY", "")) or None,
        "county_name": county.get("NAME"),
        "state": county.get("STATE"),
    }
