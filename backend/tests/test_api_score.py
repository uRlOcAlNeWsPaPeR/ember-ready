from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import score as score_module
from app.cache import db as cache_db
from app.geocode.resolver import GeocodeError
from app.main import app
from app.schemas import (
    BurnProbabilityFactor,
    FactorFailure,
    FeatureSet,
    FuelFactor,
    Location,
    Resolution,
    SearchType,
    SlopeFactor,
    WeatherFactors,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.sqlite3")
    yield


def make_features(weather=True, slope=True, fuel=True, burn_probability=True, failures=None) -> FeatureSet:
    now = datetime.now(timezone.utc)
    return FeatureSet(
        location=Location(
            latitude=39.76,
            longitude=-121.62,
            matched_address="Paradise, California, US",
            resolution=Resolution.NEIGHBORHOOD,
            source="test-source",
            search_type=SearchType.PLACE,
            county_fips="06007",
            county_name="Butte County",
            state="06",
        ),
        weather=WeatherFactors(
            temperature_c=25.0,
            relative_humidity_pct=20.0,
            wind_speed_kmh=20.0,
            wind_gusts_kmh=35.0,
            days_since_meaningful_rain=10.0,
            observed_at=now,
            source="test-weather-source",
            resolution=Resolution.GRIDDED_1_11KM,
        )
        if weather
        else None,
        slope=SlopeFactor(
            slope_pct=8.0, source="test-slope-source", resolution=Resolution.NEIGHBORHOOD, observed_at=now
        )
        if slope
        else None,
        fuel=FuelFactor(
            fuel_model_code=145,
            fuel_model_label="SH5 High load dry shrub",
            fuel_hazard_score=0.8,
            source="test-fuel-source",
            resolution=Resolution.GRIDDED_30M,
            observed_at=now,
            vintage="test-vintage",
        )
        if fuel
        else None,
        burn_probability=BurnProbabilityFactor(
            bp_national_percentile=0.9,
            county_name="Butte County",
            source="test-fire-history-source",
            resolution=Resolution.COUNTY,
            vintage="test-vintage",
        )
        if burn_probability
        else None,
        failures=failures or [],
    )


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_score_happy_path(monkeypatch):
    monkeypatch.setattr(score_module, "build_feature_set", lambda query, client: make_features())

    resp = client.get("/api/score", params={"query": "Paradise, CA", "use_cache": False})
    assert resp.status_code == 200
    body = resp.json()

    assert body["query"] == "Paradise, CA"
    assert body["search_type"] == "place"
    assert 0 <= body["preparedness_indicator"]["score"] <= 100
    assert body["preparedness_indicator"]["label"] in {"Low", "Moderate", "High", "Extreme"}
    assert 0 <= body["baseline_wildfire_exposure"]["score"] <= 100
    assert 0 <= body["current_fire_weather"]["score"] <= 100
    assert body["location"]["county_fips"] == "06007"
    assert body["location"]["location_precision_label"]
    assert len(body["factors"]) == 8
    assert body["data_quality"]["confidence"] == "High"
    assert "not an official wildfire forecast" in body["safety_notice"]
    assert "not an emergency alert system" in body["disclaimer"]
    assert "United States only" in body["us_only_notice"]
    assert body["cached"] is False
    assert body["generated_at"]


def test_score_is_cached_between_requests(monkeypatch):
    call_count = {"n": 0}

    def fake_build(query, client):
        call_count["n"] += 1
        return make_features()

    monkeypatch.setattr(score_module, "build_feature_set", fake_build)

    r1 = client.get("/api/score", params={"query": "cache-test-query"})
    r2 = client.get("/api/score", params={"query": "cache-test-query"})

    assert call_count["n"] == 1
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True
    assert r1.json()["preparedness_indicator"]["score"] == r2.json()["preparedness_indicator"]["score"]


def test_use_cache_false_bypasses_cache(monkeypatch):
    call_count = {"n": 0}

    def fake_build(query, client):
        call_count["n"] += 1
        return make_features()

    monkeypatch.setattr(score_module, "build_feature_set", fake_build)

    client.get("/api/score", params={"query": "no-cache-query", "use_cache": False})
    client.get("/api/score", params={"query": "no-cache-query", "use_cache": False})

    assert call_count["n"] == 2


def test_geocode_failure_returns_404(monkeypatch):
    def raise_geocode_error(query, client):
        raise GeocodeError("nowhere near a real address")

    monkeypatch.setattr(score_module, "build_feature_set", raise_geocode_error)

    resp = client.get("/api/score", params={"query": "asdkjfhaskjdfh", "use_cache": False})
    assert resp.status_code == 404


def test_partial_upstream_failure_degrades_gracefully_instead_of_erroring(monkeypatch):
    """A single upstream failure (e.g. LANDFIRE timing out) must not take
    down the whole request — the endpoint should still return 200 with
    that factor marked unavailable and confidence reduced."""
    monkeypatch.setattr(
        score_module,
        "build_feature_set",
        lambda query, client: make_features(
            fuel=False, failures=[FactorFailure(factor="fuel", reason="LANDFIRE WMS request timed out")]
        ),
    )

    resp = client.get("/api/score", params={"query": "Paradise, CA", "use_cache": False})
    assert resp.status_code == 200
    body = resp.json()

    fuel_factor = next(f for f in body["factors"] if f["name"] == "fuel_hazard")
    assert fuel_factor["available"] is False
    assert fuel_factor["raw_value"] is None
    assert fuel_factor["contribution_points"] == 0
    assert "LANDFIRE" in fuel_factor["unavailable_reason"]

    assert body["data_quality"]["confidence"] in {"Medium", "Low"}
    assert any(u["factor"] == "fuel_hazard" for u in body["data_quality"]["unavailable_factors"])
    # Score is still computed from what's available, not defaulted or errored out.
    assert body["baseline_wildfire_exposure"]["score"] is not None


def test_neither_query_nor_coords_is_400():
    resp = client.get("/api/score")
    assert resp.status_code == 400


def test_both_query_and_coords_is_400():
    resp = client.get("/api/score", params={"query": "Paradise, CA", "lat": 39.76, "lon": -121.62})
    assert resp.status_code == 400


def test_lat_lon_path_uses_coords_directly(monkeypatch):
    captured = {}

    def fake_location_from_coords(latitude, longitude, client):
        captured["latitude"] = latitude
        captured["longitude"] = longitude
        return make_features().location

    def fake_build_for_location(location, client):
        captured["location"] = location
        return make_features()

    monkeypatch.setattr(score_module, "_location_from_coords", fake_location_from_coords)
    monkeypatch.setattr(score_module, "build_feature_set_for_location", fake_build_for_location)

    resp = client.get("/api/score", params={"lat": 39.76, "lon": -121.62, "use_cache": False})
    assert resp.status_code == 200
    assert captured["latitude"] == 39.76
    assert captured["longitude"] == -121.62
    body = resp.json()
    assert body["query"] == "latlon:39.7600,-121.6200"
    assert body["search_type"] == "place"  # from the mocked location's search_type


def test_lat_lon_requires_both():
    resp = client.get("/api/score", params={"lat": 39.76})
    assert resp.status_code == 400


def test_location_from_coords_enriches_county(monkeypatch):
    def fake_reverse_geocode(lat, lon, client):
        return {"county_fips": "06007", "county_name": "Butte County", "state": "06"}

    monkeypatch.setattr(score_module.census, "reverse_geocode_county", fake_reverse_geocode)

    location = score_module._location_from_coords(39.76, -121.62, client=None)
    assert location.latitude == 39.76
    assert location.county_fips == "06007"
    assert location.source == "User-provided coordinates (map click)"
    assert location.search_type.value == "coordinates"


def test_location_from_coords_survives_reverse_geocode_failure(monkeypatch):
    import httpx as httpx_module

    def raise_error(lat, lon, client):
        raise httpx_module.HTTPError("boom")

    monkeypatch.setattr(score_module.census, "reverse_geocode_county", raise_error)

    location = score_module._location_from_coords(39.76, -121.62, client=None)
    assert location.county_fips is None
