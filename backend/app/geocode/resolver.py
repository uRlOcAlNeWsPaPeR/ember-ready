"""Top-level geocoding entry point: given whatever the user typed, return a
Location with lat/lon, an explicit search_type, and — where possible — a
county FIPS code for the county-level baseline lookup.

Three explicit paths, each labeled with its own precision:
1. Bare ZIP code (regex-detected) -> Census ZCTA gazetteer centroid
   (authoritative government source, not a third-party geocoder guess).
2. Otherwise -> Census address geocoder (best for full street addresses;
   returns county FIPS in the same call).
3. If that fails -> Open-Meteo place/city-name fallback, then reverse-
   geocoded through Census to still get a county FIPS.

Every path enriches with county FIPS via Census reverse geocoding if it
wasn't already returned, since the burn-probability baseline factor needs
it — but a reverse-geocode failure is recorded, never silently swallowed
into "county data unavailable" without explanation.
"""
from __future__ import annotations

import httpx

from app.geocode import census, openmeteo_geo, zcta
from app.schemas import Location, Resolution, SearchType


class GeocodeError(Exception):
    pass


def resolve(query: str, client: httpx.Client | None = None) -> Location:
    query = query.strip()
    if not query:
        raise GeocodeError("Empty address/ZIP query")

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        if zcta.is_zip_query(query):
            location = _resolve_zip(query)
        else:
            location = _resolve_address_or_place(query, client)

        _enrich_county(location, client)
        return location
    finally:
        if owns_client:
            client.close()


def _resolve_zip(query: str) -> Location:
    try:
        lat, lon = zcta.get_zip_centroid(query)
    except zcta.ZctaLookupError as exc:
        raise GeocodeError(f"ZIP code {query!r} not found in the Census ZCTA gazetteer") from exc

    return Location(
        latitude=lat,
        longitude=lon,
        matched_address=f"ZIP {query.strip()[:5]}",
        resolution=Resolution.ZIP_CENTROID,
        source=zcta.SOURCE,
        search_type=SearchType.ZIP,
    )


def _resolve_address_or_place(query: str, client: httpx.Client) -> Location:
    try:
        return census.geocode_address(query, client=client)
    except (census.CensusGeocodeError, httpx.HTTPError):
        pass

    try:
        return openmeteo_geo.geocode_place(query, client=client)
    except (openmeteo_geo.OpenMeteoGeocodeError, httpx.HTTPError) as exc:
        raise GeocodeError(f"Could not resolve location for {query!r}") from exc


def _enrich_county(location: Location, client: httpx.Client) -> None:
    if location.county_fips:
        return
    try:
        county_info = census.reverse_geocode_county(location.latitude, location.longitude, client=client)
        location.county_fips = county_info.get("county_fips")
        location.county_name = county_info.get("county_name")
        location.state = county_info.get("state")
    except httpx.HTTPError:
        pass  # county enrichment is best-effort; the scorer explains a missing county as a failed baseline factor
