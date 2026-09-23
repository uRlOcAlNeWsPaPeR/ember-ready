import httpx
import pytest
import respx

from app.geocode import census, openmeteo_geo
from app.geocode.resolver import GeocodeError, resolve
from app.schemas import Resolution, SearchType

CENSUS_ADDRESS_URL = f"{census.BASE_URL}/geographies/onelineaddress"
CENSUS_COORDS_URL = f"{census.BASE_URL}/geographies/coordinates"
OM_GEOCODE_URL = openmeteo_geo.BASE_URL


def census_address_match():
    return httpx.Response(
        200,
        json={
            "result": {
                "addressMatches": [
                    {
                        "matchedAddress": "195 BUCHANAN ST, SAN FRANCISCO, CA, 94102",
                        "coordinates": {"x": -122.427, "y": 37.7715},
                        "geographies": {
                            "Counties": [
                                {"STATE": "06", "COUNTY": "075", "NAME": "San Francisco County"}
                            ]
                        },
                    }
                ]
            }
        },
    )


def census_no_match():
    return httpx.Response(200, json={"result": {"addressMatches": []}})


def census_coords_match():
    return httpx.Response(
        200,
        json={
            "result": {
                "geographies": {
                    "Counties": [{"STATE": "06", "COUNTY": "007", "NAME": "Butte County"}]
                }
            }
        },
    )


def openmeteo_place_match():
    return httpx.Response(
        200,
        json={
            "results": [
                {
                    "latitude": 39.76,
                    "longitude": -121.62,
                    "name": "Paradise",
                    "admin1": "California",
                    "country_code": "US",
                }
            ]
        },
    )


@respx.mock
def test_full_address_resolves_via_census_only():
    respx.get(CENSUS_ADDRESS_URL).mock(return_value=census_address_match())
    location = resolve("195 Buchanan St, San Francisco, CA 94102")
    assert location.county_fips == "06075"
    assert location.resolution == Resolution.POINT
    assert location.search_type == SearchType.ADDRESS
    assert location.source.startswith("US Census")


def test_bare_zip_resolves_via_zcta_gazetteer_never_calling_census_or_openmeteo():
    # No respx mocks registered at all — if the resolver made any live HTTP
    # call for the ZIP lookup itself, this would fail with a connection error.
    with respx.mock:
        respx.get(CENSUS_COORDS_URL).mock(return_value=census_coords_match())
        location = resolve("95969")

    assert location.search_type == SearchType.ZIP
    assert location.resolution == Resolution.ZIP_CENTROID
    assert location.county_fips == "06007"
    assert location.latitude == pytest.approx(39.720742, abs=0.01)
    assert "Census" in location.source
    assert "approximate" in location.location_precision_label.lower()
    assert "not property-specific" in location.location_precision_label.lower()


def test_zip_plus_four_uses_five_digit_zcta():
    with respx.mock:
        respx.get(CENSUS_COORDS_URL).mock(return_value=census_coords_match())
        location = resolve("95969-1234")
    assert location.search_type == SearchType.ZIP
    assert location.latitude == pytest.approx(39.720742, abs=0.01)


@respx.mock
def test_unmatched_address_falls_back_to_openmeteo_place_search():
    respx.get(CENSUS_ADDRESS_URL).mock(return_value=census_no_match())
    respx.get(OM_GEOCODE_URL).mock(return_value=openmeteo_place_match())
    respx.get(CENSUS_COORDS_URL).mock(return_value=census_coords_match())

    location = resolve("Paradise, CA")
    assert location.latitude == 39.76
    assert location.county_fips == "06007"
    assert location.resolution == Resolution.NEIGHBORHOOD
    assert location.search_type == SearchType.PLACE


@respx.mock
def test_no_match_anywhere_raises_geocode_error():
    respx.get(CENSUS_ADDRESS_URL).mock(return_value=census_no_match())
    respx.get(OM_GEOCODE_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    try:
        resolve("not a real place at all")
        assert False, "expected GeocodeError"
    except GeocodeError:
        pass


def test_unknown_zip_raises_geocode_error():
    try:
        resolve("00000")
        assert False, "expected GeocodeError"
    except GeocodeError:
        pass


def test_empty_query_raises():
    try:
        resolve("   ")
        assert False, "expected GeocodeError"
    except GeocodeError:
        pass
