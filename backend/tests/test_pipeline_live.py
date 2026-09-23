"""End-to-end check against the real external APIs (Census, Census ZCTA
gazetteer (local, no live call), Open-Meteo, USGS EPQS, LANDFIRE WMS, WRC
county CSV). Skipped by default since a hackathon demo/grading environment
shouldn't fail on network flakiness; run explicitly with RUN_LIVE_TESTS=1
to sanity-check real integrations.
"""
import os

import pytest

from app.pipeline import build_feature_set
from app.schemas import SearchType
from app.scoring.weighted_model import WeightedRiskModel

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to hit real external APIs"
)


def test_full_pipeline_for_a_real_address():
    features = build_feature_set("195 Buchanan St, San Francisco, CA 94102")
    assert features.location.county_fips == "06075"
    assert features.location.search_type == SearchType.ADDRESS
    assert features.weather is not None
    assert -10 < features.weather.temperature_c < 55
    assert 0 <= features.weather.relative_humidity_pct <= 100
    assert features.fuel is not None
    assert features.fuel.fuel_model_code > 0

    result = WeightedRiskModel().score(features)
    assert 0 <= result.preparedness_indicator.score <= 100
    assert result.preparedness_indicator.label in {"Low", "Moderate", "High", "Extreme"}
    assert result.baseline_wildfire_exposure.score is not None
    assert result.current_fire_weather.score is not None
    assert result.data_quality.confidence.value in {"High", "Medium", "Low"}


def test_full_pipeline_for_a_zip_code_uses_zcta_gazetteer():
    features = build_feature_set("95969")
    assert features.location.search_type == SearchType.ZIP
    assert "zip" in features.location.resolution.value

    result = WeightedRiskModel().score(features)
    assert 0 <= result.preparedness_indicator.score <= 100
    # A ZIP search should never be silently treated as address-precision.
    assert "approximate" in features.location.location_precision_label.lower()
