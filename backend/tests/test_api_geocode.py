from fastapi.testclient import TestClient

from app.api import geocode as geocode_module
from app.main import app

client = TestClient(app)


def test_suggest_happy_path(monkeypatch):
    monkeypatch.setattr(
        geocode_module,
        "search_suggestions",
        lambda q, count, client: [{"label": "Denver, Colorado, US", "latitude": 39.7, "longitude": -104.9}],
    )
    resp = client.get("/api/geocode/suggest", params={"q": "Denv"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggestions"][0]["label"] == "Denver, Colorado, US"


def test_suggest_short_query_returns_empty_without_calling_upstream(monkeypatch):
    called = {"n": 0}

    def fake_search(q, count, client):
        called["n"] += 1
        return []

    monkeypatch.setattr(geocode_module, "search_suggestions", fake_search)
    resp = client.get("/api/geocode/suggest", params={"q": "D"})
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []
    assert called["n"] == 0


def test_suggest_upstream_failure_returns_empty_not_error(monkeypatch):
    import httpx

    def raise_error(q, count, client):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(geocode_module, "search_suggestions", raise_error)
    resp = client.get("/api/geocode/suggest", params={"q": "Denver"})
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_missing_query_is_422():
    resp = client.get("/api/geocode/suggest")
    assert resp.status_code == 422
