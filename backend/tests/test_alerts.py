import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.weather.alerts import BASE_URL, AlertsFetchError, get_active_alerts

client = TestClient(app)


def alert_feature(event, headline="Test headline", severity="Severe", area_desc="Test County"):
    return {
        "properties": {
            "@id": "https://api.weather.gov/alerts/urn:test",
            "event": event,
            "headline": headline,
            "severity": severity,
            "urgency": "Immediate",
            "areaDesc": area_desc,
            "effective": "2026-09-22T20:20:00-05:00",
            "expires": "2026-09-22T23:20:00-05:00",
        }
    }


def alerts_response(features):
    return httpx.Response(200, json={"features": features})


@respx.mock
def test_no_active_alerts():
    respx.get(BASE_URL).mock(return_value=alerts_response([]))
    readings = get_active_alerts(39.76, -121.62)
    assert readings == []


@respx.mock
def test_fire_related_alert_flagged():
    respx.get(BASE_URL).mock(return_value=alerts_response([alert_feature("Red Flag Warning")]))
    readings = get_active_alerts(39.76, -121.62)
    assert len(readings) == 1
    assert readings[0].is_fire_related is True
    assert readings[0].event == "Red Flag Warning"


@respx.mock
def test_non_fire_alert_not_flagged():
    respx.get(BASE_URL).mock(return_value=alerts_response([alert_feature("Flood Warning")]))
    readings = get_active_alerts(39.76, -121.62)
    assert readings[0].is_fire_related is False


@respx.mock
def test_api_endpoint_happy_path():
    respx.get(BASE_URL).mock(return_value=alerts_response([alert_feature("Fire Weather Watch")]))
    resp = client.get("/api/alerts", params={"lat": 39.76, "lon": -121.62})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["is_fire_related"] is True
    assert "National Weather Service" in body["source"]


@respx.mock
def test_api_endpoint_upstream_failure():
    respx.get(BASE_URL).mock(return_value=httpx.Response(500))
    resp = client.get("/api/alerts", params={"lat": 39.76, "lon": -121.62})
    assert resp.status_code == 502


def test_fetch_error_on_http_error():
    with respx.mock:
        respx.get(BASE_URL).mock(side_effect=httpx.ConnectError("boom"))
        try:
            get_active_alerts(39.76, -121.62)
            assert False, "expected AlertsFetchError"
        except AlertsFetchError:
            pass
