import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAYLOAD = {
    "location": "Paradise, CA",
    "status_label": "High Risk",
    "baseline_label": "High",
    "weather_label": "Moderate",
    "factors": [
        {"name": "wind_gusts", "available": True, "raw_value": 42.0, "raw_unit": "km/h", "contribution_points": 8.0},
        {"name": "burn_probability", "available": False, "raw_value": None, "raw_unit": None, "contribution_points": None},
    ],
    "safety_notice": "This reflects fire-weather conditions, not a confirmed fire detection.",
}


def gemini_response(text):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_explain_returns_503_when_no_api_key(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", None)
    resp = client.post("/api/explain", json=PAYLOAD)
    assert resp.status_code == 503


@respx.mock
def test_explain_happy_path(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", "test-key")
    respx.post(ai_explain_module.GEMINI_URL).mock(
        return_value=gemini_response("Strong wind gusts are the main driver of today's elevated risk.")
    )
    resp = client.post("/api/explain", json=PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert "wind gusts" in body["explanation"]
    assert body["model"] == ai_explain_module.GEMINI_MODEL


@respx.mock
def test_explain_upstream_failure_returns_502(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", "test-key")
    respx.post(ai_explain_module.GEMINI_URL).mock(return_value=httpx.Response(500))
    resp = client.post("/api/explain", json=PAYLOAD)
    assert resp.status_code == 502


@respx.mock
def test_explain_quota_exceeded_returns_429_with_user_facing_message(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", "test-key")
    respx.post(ai_explain_module.GEMINI_URL).mock(return_value=httpx.Response(429))
    resp = client.post("/api/explain", json=PAYLOAD)
    assert resp.status_code == 429
    assert resp.json()["detail"] == ai_explain_module.QUOTA_MESSAGE
    assert "free" in resp.json()["detail"].lower()


PLAN_PAYLOAD = {
    "hazard": "earthquake",
    "items": [
        {"category": "earthquakeBefore", "text": "Secure heavy furniture to walls.", "done": True},
        {"category": "earthquakeBefore", "text": "Pack a go-bag.", "done": False},
    ],
}


def test_plan_summary_returns_503_when_no_api_key(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", None)
    resp = client.post("/api/plan-summary", json=PLAN_PAYLOAD)
    assert resp.status_code == 503


@respx.mock
def test_plan_summary_happy_path(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", "test-key")
    respx.post(ai_explain_module.GEMINI_URL).mock(
        return_value=gemini_response("Great start securing your furniture — packing a go-bag is a good next step.")
    )
    resp = client.post("/api/plan-summary", json=PLAN_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert "go-bag" in body["summary"]
    assert body["model"] == ai_explain_module.GEMINI_MODEL


@respx.mock
def test_plan_summary_upstream_failure_returns_502(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", "test-key")
    respx.post(ai_explain_module.GEMINI_URL).mock(return_value=httpx.Response(500))
    resp = client.post("/api/plan-summary", json=PLAN_PAYLOAD)
    assert resp.status_code == 502


@respx.mock
def test_plan_summary_quota_exceeded_returns_429_with_user_facing_message(monkeypatch):
    import app.api.ai_explain as ai_explain_module

    monkeypatch.setattr(ai_explain_module, "GEMINI_API_KEY", "test-key")
    respx.post(ai_explain_module.GEMINI_URL).mock(return_value=httpx.Response(429))
    resp = client.post("/api/plan-summary", json=PLAN_PAYLOAD)
    assert resp.status_code == 429
    assert resp.json()["detail"] == ai_explain_module.QUOTA_MESSAGE
