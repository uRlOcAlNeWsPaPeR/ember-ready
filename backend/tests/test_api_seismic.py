from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_seismic_grid_returns_geojson_with_cache_header():
    resp = client.get("/api/seismic/grid")
    assert resp.status_code == 200
    assert "max-age" in resp.headers.get("cache-control", "")
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 100
    feature = body["features"][0]
    assert feature["properties"]["category"] in {"Low", "Moderate", "High", "Very High"}
    assert feature["geometry"]["type"] == "Polygon"


def test_get_seismic_meta_has_legend_and_disclaimer():
    resp = client.get("/api/seismic/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert "not a prediction" in body["disclaimer"]
    labels = {entry["label"] for entry in body["legend"]}
    assert labels == {"Low", "Moderate", "High", "Very High"}
    assert "USGS" in body["source"]


def test_get_seismic_grid_missing_file_returns_503(monkeypatch, tmp_path):
    import app.api.seismic as seismic_module

    monkeypatch.setattr(seismic_module, "GRID_DATA_PATH", tmp_path / "does-not-exist.geojson")
    resp = client.get("/api/seismic/grid")
    assert resp.status_code == 503
