from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_counties_returns_geojson_with_cache_header():
    resp = client.get("/api/map/counties")
    assert resp.status_code == 200
    assert "max-age" in resp.headers.get("cache-control", "")
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 3000


def test_get_map_meta_has_legend_and_disclaimer():
    resp = client.get("/api/map/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution"] == "county"
    assert "Baseline hazard only" in body["disclaimer"]
    labels = {entry["label"] for entry in body["legend"]}
    assert labels == {"Low", "Moderate", "High", "Extreme", "No data"}
    assert body["hazard_source"]
    assert body["boundaries_source"]


def test_get_counties_missing_file_returns_503(monkeypatch, tmp_path):
    import app.api.map as map_module

    monkeypatch.setattr(map_module, "MAP_DATA_PATH", tmp_path / "does-not-exist.geojson")
    resp = client.get("/api/map/counties")
    assert resp.status_code == 503
