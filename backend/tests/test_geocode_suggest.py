import httpx
import respx

from app.geocode.openmeteo_geo import BASE_URL, search_suggestions


def om_response(results):
    return httpx.Response(200, json={"results": results})


@respx.mock
def test_search_suggestions_returns_labeled_results():
    respx.get(BASE_URL).mock(
        return_value=om_response(
            [
                {"name": "Denver", "admin1": "Colorado", "country_code": "US", "latitude": 39.7, "longitude": -104.9},
                {"name": "Denver City", "admin1": "Texas", "country_code": "US", "latitude": 32.9, "longitude": -102.8},
            ]
        )
    )
    results = search_suggestions("Denv", count=5)
    assert len(results) == 2
    assert results[0]["label"] == "Denver, Colorado, US"
    assert results[0]["latitude"] == 39.7


@respx.mock
def test_search_suggestions_empty_when_no_matches():
    respx.get(BASE_URL).mock(return_value=om_response([]))
    assert search_suggestions("zzzzzz") == []
