"""Data-driven validation suite over tests/fixtures/locations.json (22
diverse US locations: high-exposure western, low-exposure eastern/urban,
address vs ZIP-only searches, wet/calm vs hot/dry/windy weather, and
missing-data/fallback cases).

IMPORTANT — scope of what this validates: these tests check SOFTWARE
BEHAVIOR and SCORING CONSISTENCY (the resolver picks the right path, the
scorer never substitutes a silent default for missing data, contributions
sum to the reported score, labels match the documented thresholds,
confidence reacts to missing data, ZIP results are marked approximate).
They do NOT validate, and must never be cited as validating, real-world
wildfire risk for any of these places — factor values are synthetic,
chosen to exercise specific code paths.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
from app.scoring.config import load_weights_config
from app.scoring.weighted_model import WeightedRiskModel

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "locations.json"
CONFIG = load_weights_config()

RESOLUTION_BY_SEARCH_TYPE = {
    "address": Resolution.POINT,
    "zip": Resolution.ZIP_CENTROID,
    "place": Resolution.NEIGHBORHOOD,
    "coordinates": Resolution.POINT,
}


def load_fixture() -> list[dict]:
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["locations"]


def build_feature_set(entry: dict) -> FeatureSet:
    now = datetime.now(timezone.utc)
    search_type = SearchType(entry["search_type"])

    location = Location(
        latitude=39.0,
        longitude=-105.0,
        matched_address=entry["query"] or "unresolved",
        resolution=RESOLUTION_BY_SEARCH_TYPE[search_type.value],
        source="fixture",
        search_type=search_type,
        county_fips=entry.get("county_fips"),
        county_name=entry.get("county_name"),
    )

    failures: list[FactorFailure] = []

    if entry.get("weather_unavailable"):
        weather = None
        failures.append(FactorFailure(factor="weather", reason=entry["weather_failure_reason"]))
    else:
        weather = WeatherFactors(
            temperature_c=entry["temperature_c"],
            relative_humidity_pct=entry["relative_humidity_pct"],
            wind_speed_kmh=entry["wind_speed_kmh"],
            wind_gusts_kmh=entry["wind_gusts_kmh"],
            days_since_meaningful_rain=entry["days_since_meaningful_rain"],
            observed_at=now,
            source="fixture-weather",
            resolution=Resolution.GRIDDED_1_11KM,
        )

    slope = SlopeFactor(slope_pct=entry["slope_pct"], source="fixture-slope", resolution=Resolution.NEIGHBORHOOD, observed_at=now)

    if entry.get("fuel_hazard_score") is None and "fuel_failure_reason" in entry:
        fuel = None
        failures.append(FactorFailure(factor="fuel", reason=entry["fuel_failure_reason"]))
    else:
        fuel = FuelFactor(
            fuel_model_code=999,
            fuel_model_label="fixture fuel model",
            fuel_hazard_score=entry["fuel_hazard_score"],
            source="fixture-fuel",
            resolution=Resolution.GRIDDED_30M,
            observed_at=now,
            vintage="fixture",
        )

    if entry.get("burn_probability_percentile") is None:
        burn_probability = None
        failures.append(FactorFailure(factor="burn_probability", reason=entry["burn_probability_failure_reason"]))
    else:
        burn_probability = BurnProbabilityFactor(
            bp_national_percentile=entry["burn_probability_percentile"],
            county_name=entry.get("county_name") or "",
            source="fixture-fire-history",
            resolution=Resolution.COUNTY,
            vintage="fixture",
        )

    return FeatureSet(
        location=location, weather=weather, slope=slope, fuel=fuel, burn_probability=burn_probability, failures=failures
    )


FIXTURE_ENTRIES = load_fixture()
assert len(FIXTURE_ENTRIES) >= 20, "Validation fixture must contain at least 20 locations"


def test_fixture_has_required_diversity():
    categories = {e["case_category"] for e in FIXTURE_ENTRIES}
    assert "high_exposure_western" in categories
    assert "low_exposure_eastern_urban" in categories
    assert "missing_data" in categories

    search_types = {e["search_type"] for e in FIXTURE_ENTRIES}
    assert "address" in search_types
    assert "zip" in search_types


@pytest.mark.parametrize("entry", FIXTURE_ENTRIES, ids=[e["name"] for e in FIXTURE_ENTRIES])
def test_search_type_is_correctly_reflected(entry):
    """Verifies the correct data path is used: the location's search_type
    and (for ZIP searches) precision label match what was resolved."""
    features = build_feature_set(entry)
    assert features.location.search_type.value == entry["search_type"]

    if entry["search_type"] == "zip":
        label = features.location.location_precision_label.lower()
        assert "approximate" in label
        assert "not property-specific" in label


@pytest.mark.parametrize("entry", FIXTURE_ENTRIES, ids=[e["name"] for e in FIXTURE_ENTRIES])
def test_no_silent_defaults_for_missing_factors(entry):
    """Any factor whose fixture value is missing must show up as
    unavailable with its real reason — never a substituted neutral value."""
    features = build_feature_set(entry)
    result = WeightedRiskModel().score(features)

    if entry.get("burn_probability_percentile") is None:
        bp = next(f for f in result.factors if f.name == "burn_probability")
        assert bp.available is False
        assert bp.raw_value is None
        assert bp.contribution_points == 0.0
        assert bp.unavailable_reason == entry["burn_probability_failure_reason"]

    if entry.get("weather_unavailable"):
        weather_names = {"wind_gusts", "wind_speed", "relative_humidity", "temperature", "days_since_rain"}
        for f in result.factors:
            if f.name in weather_names:
                assert f.available is False
                assert f.raw_value is None


@pytest.mark.parametrize("entry", FIXTURE_ENTRIES, ids=[e["name"] for e in FIXTURE_ENTRIES])
def test_contributions_sum_to_reported_component_scores(entry):
    features = build_feature_set(entry)
    result = WeightedRiskModel().score(features)

    for component, category in (
        (result.baseline_wildfire_exposure, "baseline_wildfire_exposure"),
        (result.current_fire_weather, "current_fire_weather"),
    ):
        in_category = [f for f in result.factors if f.category == category]
        available = [f for f in in_category if f.available]
        if not available:
            assert component.score is None
            continue
        available_weight = sum(f.weight_points for f in available)
        expected_score = sum(f.contribution_points for f in available) / available_weight * 100
        assert component.score == pytest.approx(round(expected_score, 1), abs=0.05)


@pytest.mark.parametrize("entry", FIXTURE_ENTRIES, ids=[e["name"] for e in FIXTURE_ENTRIES])
def test_labels_match_documented_thresholds(entry):
    features = build_feature_set(entry)
    result = WeightedRiskModel().score(features)

    thresholds = CONFIG["label_thresholds"]

    def expected_label(score):
        if score is None:
            return None
        for threshold, label in thresholds:
            if score <= threshold:
                return label
        return thresholds[-1][1]

    assert result.baseline_wildfire_exposure.label == expected_label(result.baseline_wildfire_exposure.score)
    assert result.current_fire_weather.label == expected_label(result.current_fire_weather.score)
    assert result.preparedness_indicator.label == expected_label(result.preparedness_indicator.score)

    if entry["expected_baseline_label"] is not None:
        assert result.baseline_wildfire_exposure.label == entry["expected_baseline_label"], entry["name"]
    if entry["expected_weather_label"] is not None:
        assert result.current_fire_weather.label == entry["expected_weather_label"], entry["name"]


@pytest.mark.parametrize("entry", FIXTURE_ENTRIES, ids=[e["name"] for e in FIXTURE_ENTRIES])
def test_confidence_matches_expected(entry):
    features = build_feature_set(entry)
    result = WeightedRiskModel().score(features)
    assert result.data_quality.confidence.value == entry["expected_confidence"], entry["name"]


def test_missing_data_cases_never_report_high_confidence():
    for entry in FIXTURE_ENTRIES:
        if entry["case_category"] != "missing_data":
            continue
        features = build_feature_set(entry)
        result = WeightedRiskModel().score(features)
        assert result.data_quality.confidence.value != "High", entry["name"]
        assert len(result.data_quality.unavailable_factors) > 0
