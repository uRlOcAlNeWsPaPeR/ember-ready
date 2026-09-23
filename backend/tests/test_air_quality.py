import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.weather.air_quality import BASE_URL, AirQualityFetchError, get_current_air_quality

client = TestClient(app)


def aq_response(us_aqi, pm2_5=10.0, pm10=15.0):
    return httpx.Response(
        200,
        json={"current": {"time": "2026-09-22T09:00", "us_aqi": us_aqi, "pm2_5": pm2_5, "pm10": pm10}},
    )


@respx.mock
def test_good_aqi_category():
    respx.get(BASE_URL).mock(return_value=aq_response(30))
    reading = get_current_air_quality(39.76, -121.62)
    assert reading.category == "Good"


@respx.mock
def test_unhealthy_aqi_category():
    respx.get(BASE_URL).mock(return_value=aq_response(175))
    reading = get_current_air_quality(39.76, -121.62)
    assert reading.category == "Unhealthy"


@respx.mock
def test_hazardous_aqi_category():
    respx.get(BASE_URL).mock(return_value=aq_response(350))
    reading = get_current_air_quality(39.76, -121.62)
    assert reading.category == "Hazardous"


@respx.mock
def test_api_endpoint_happy_path():
    respx.get(BASE_URL).mock(return_value=aq_response(60))
    resp = client.get("/api/air-quality", params={"lat": 39.76, "lon": -121.62})
    assert resp.status_code == 200
    body = resp.json()
    assert body["us_aqi"] == 60
    assert body["category"] == "Moderate"
    assert "not a wildfire risk input" in body["note"]


@respx.mock
def test_api_endpoint_upstream_failure():
    respx.get(BASE_URL).mock(return_value=httpx.Response(500))
    resp = client.get("/api/air-quality", params={"lat": 39.76, "lon": -121.62})
    assert resp.status_code == 502


def test_fetch_error_on_missing_field():
    import respx as respx_module

    with respx_module.mock:
        respx_module.get(BASE_URL).mock(return_value=httpx.Response(200, json={"current": {}}))
        try:
            get_current_air_quality(39.76, -121.62)
            assert False, "expected AirQualityFetchError"
        except AirQualityFetchError:
            pass
