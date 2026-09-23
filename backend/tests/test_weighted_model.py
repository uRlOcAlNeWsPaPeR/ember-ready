from datetime import datetime, timezone

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

CONFIG = load_weights_config()


def make_location(**overrides) -> Location:
    defaults = dict(
        latitude=39.76,
        longitude=-121.62,
        matched_address="Paradise, CA",
        resolution=Resolution.POINT,
        source="test",
        search_type=SearchType.ADDRESS,
        county_fips="06007",
    )
    defaults.update(overrides)
    return Location(**defaults)


def make_weather(**overrides) -> WeatherFactors:
    now = datetime.now(timezone.utc)
    defaults = dict(
        temperature_c=20.0,
        relative_humidity_pct=50.0,
        wind_speed_kmh=15.0,
        wind_gusts_kmh=25.0,
        days_since_meaningful_rain=5.0,
        observed_at=now,
        source="test-weather",
        resolution=Resolution.GRIDDED_1_11KM,
    )
    defaults.update(overrides)
    return WeatherFactors(**defaults)


def make_slope(**overrides) -> SlopeFactor:
    defaults = dict(
        slope_pct=10.0, source="test-slope", resolution=Resolution.NEIGHBORHOOD, observed_at=datetime.now(timezone.utc)
    )
    defaults.update(overrides)
    return SlopeFactor(**defaults)


def make_fuel(**overrides) -> FuelFactor:
    defaults = dict(
        fuel_model_code=145,
        fuel_model_label="SH5 High load dry shrub",
        fuel_hazard_score=0.8,
        source="test-fuel",
        resolution=Resolution.GRIDDED_30M,
        observed_at=datetime.now(timezone.utc),
        vintage="test-vintage",
    )
    defaults.update(overrides)
    return FuelFactor(**defaults)


def make_burn_probability(**overrides) -> BurnProbabilityFactor:
    defaults = dict(
        bp_national_percentile=0.6,
        county_name="Butte County, CA",
        source="test-fire-history",
        resolution=Resolution.COUNTY,
        vintage="test-vintage",
    )
    defaults.update(overrides)
    return BurnProbabilityFactor(**defaults)


_UNSET = object()


def make_features(weather=_UNSET, slope=_UNSET, fuel=_UNSET, burn_probability=_UNSET, failures=None, location=None) -> FeatureSet:
    return FeatureSet(
        location=location or make_location(),
        weather=make_weather() if weather is _UNSET else weather,
        slope=make_slope() if slope is _UNSET else slope,
        fuel=make_fuel() if fuel is _UNSET else fuel,
        burn_probability=make_burn_probability() if burn_probability is _UNSET else burn_probability,
        failures=failures or [],
    )


def test_config_weights_sum_to_100():
    total = sum(f["weight_points"] for f in CONFIG["factors"].values())
    assert abs(total - 100.0) < 1e-9


def test_full_data_produces_all_three_components():
    model = WeightedRiskModel()
    result = model.score(make_features())

    assert result.baseline_wildfire_exposure.score is not None
    assert result.current_fire_weather.score is not None
    assert result.preparedness_indicator.score is not None
    assert result.data_quality.confidence.value == "High"
    assert result.data_quality.factors_available == 8
    assert len(result.factors) == 8


def test_high_baseline_survives_calm_weather():
    """The whole point of separating the two concepts: a high baseline
    exposure must still be clearly visible even when today's weather is
    mild — not averaged away into a falsely reassuring single number."""
    model = WeightedRiskModel()
    result = model.score(
        make_features(
            burn_probability=make_burn_probability(bp_national_percentile=0.95),
            fuel=make_fuel(fuel_hazard_score=0.9),
            slope=make_slope(slope_pct=40.0),
            weather=make_weather(
                temperature_c=15.0,
                relative_humidity_pct=80.0,
                wind_speed_kmh=5.0,
                wind_gusts_kmh=8.0,
                days_since_meaningful_rain=0.0,
            ),
        )
    )
    assert result.baseline_wildfire_exposure.label in {"High", "Extreme"}
    assert result.baseline_wildfire_exposure.score > 85
    # Combined score reflects the calm weather too, but never hides the baseline component.
    assert result.preparedness_indicator.score < result.baseline_wildfire_exposure.score


def test_missing_burn_probability_is_excluded_not_defaulted():
    model = WeightedRiskModel()
    result = model.score(
        make_features(
            burn_probability=None,
            failures=[FactorFailure(factor="burn_probability", reason="County not found in WRC table")],
        )
    )
    bp_factor = next(f for f in result.factors if f.name == "burn_probability")
    assert bp_factor.available is False
    assert bp_factor.raw_value is None
    assert bp_factor.contribution_points == 0.0
    assert bp_factor.unavailable_reason == "County not found in WRC table"

    # Baseline score is computed only from fuel + slope, rescaled to 0-100 —
    # never silently substituting a neutral value for burn probability.
    assert result.baseline_wildfire_exposure.score is not None
    assert result.baseline_wildfire_exposure.available_weight_pct == pytest.approx((30 / 65) * 100, abs=0.1)
    assert result.data_quality.confidence.value in {"Medium", "Low"}
    assert any(u.factor == "burn_probability" for u in result.data_quality.unavailable_factors)


def test_missing_entire_weather_category():
    model = WeightedRiskModel()
    result = model.score(make_features(weather=None, failures=[FactorFailure(factor="weather", reason="Open-Meteo timed out")]))

    assert result.current_fire_weather.score is None
    assert result.current_fire_weather.label is None
    assert result.baseline_wildfire_exposure.score is not None
    # With weather entirely missing, the indicator falls back to baseline alone.
    assert result.preparedness_indicator.score == result.baseline_wildfire_exposure.score
    assert result.data_quality.confidence.value == "Low"
    weather_factor_names = {"wind_gusts", "wind_speed", "relative_humidity", "temperature", "days_since_rain"}
    assert all(
        not f.available for f in result.factors if f.name in weather_factor_names
    )


def test_missing_everything_in_a_category_and_the_other():
    model = WeightedRiskModel()
    result = model.score(
        make_features(
            weather=None,
            slope=None,
            fuel=None,
            burn_probability=None,
            failures=[
                FactorFailure(factor="weather", reason="x"),
                FactorFailure(factor="slope", reason="x"),
                FactorFailure(factor="fuel", reason="x"),
                FactorFailure(factor="burn_probability", reason="x"),
            ],
        )
    )
    assert result.baseline_wildfire_exposure.score is None
    assert result.current_fire_weather.score is None
    assert result.preparedness_indicator.score is None
    assert result.data_quality.confidence.value == "Low"
    assert result.data_quality.factors_available == 0


def test_every_available_factor_reports_source_and_resolution():
    model = WeightedRiskModel()
    result = model.score(make_features())
    for factor in result.factors:
        assert factor.available
        assert factor.source
        assert factor.resolution is not None
        assert factor.contribution_points == pytest.approx(factor.normalized_value * factor.weight_points)


def test_zip_search_marks_fallback_only_for_place_not_zip():
    model = WeightedRiskModel()
    zip_location = make_location(resolution=Resolution.ZIP_CENTROID, search_type=SearchType.ZIP)
    result = model.score(make_features(location=zip_location))
    assert result.data_quality.fallback_used is False

    place_location = make_location(resolution=Resolution.NEIGHBORHOOD, search_type=SearchType.PLACE)
    result2 = model.score(make_features(location=place_location))
    assert result2.data_quality.fallback_used is True
