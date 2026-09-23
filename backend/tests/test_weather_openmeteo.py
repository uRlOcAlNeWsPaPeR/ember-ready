import httpx
import respx

from app.scoring.config import load_weights_config
from app.weather.openmeteo import (
    BASE_URL,
    WeatherFetchError,
    _days_since_meaningful_rain,
    get_current_conditions,
)

CONFIG = load_weights_config()
MEANINGFUL_RAIN_MM = CONFIG["meaningful_rain_mm"]
LOOKBACK_DAYS = CONFIG["rain_lookback_days"]


def make_response(precip_sum, current_overrides=None):
    n = len(precip_sum)
    dates = [f"2026-09-{i+1:02d}" for i in range(n)]
    current = {
        "time": "2026-09-21T12:00",
        "temperature_2m": 32.0,
        "relative_humidity_2m": 12.0,
        "wind_speed_10m": 45.0,
        "wind_gusts_10m": 70.0,
        "wind_direction_10m": 270.0,
    }
    if current_overrides:
        current.update(current_overrides)
    return {
        "current": current,
        "daily": {"time": dates, "precipitation_sum": precip_sum},
    }


def test_documented_threshold_matches_config():
    # Locks in the documented threshold from the scoring requirements:
    # >=2.5mm / 0.1in daily precipitation counts as "meaningful rain."
    assert MEANINGFUL_RAIN_MM == 2.5


@respx.mock
def test_get_current_conditions_happy_path():
    precip = [0.0] * (LOOKBACK_DAYS - 4) + [0, 0, 0, MEANINGFUL_RAIN_MM + 1, 0]
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=make_response(precip)))
    reading = get_current_conditions(37.77, -122.42)
    assert reading.temperature_c == 32.0
    assert reading.relative_humidity_pct == 12.0
    assert reading.wind_speed_kmh == 45.0
    assert reading.wind_gusts_kmh == 70.0
    assert reading.wind_direction_deg == 270.0
    assert reading.days_since_meaningful_rain == 1.0


@respx.mock
def test_no_rain_in_window_caps_at_lookback_days():
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=make_response([0.0] * (LOOKBACK_DAYS + 1))))
    reading = get_current_conditions(37.77, -122.42)
    assert reading.days_since_meaningful_rain == float(LOOKBACK_DAYS)


@respx.mock
def test_rain_today_is_zero_days_since():
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=make_response([0, 0, MEANINGFUL_RAIN_MM])))
    reading = get_current_conditions(37.77, -122.42)
    assert reading.days_since_meaningful_rain == 0.0


@respx.mock
def test_below_threshold_rain_does_not_count_as_meaningful():
    # Rain that doesn't clear the documented 2.5mm threshold must not reset the dry-spell counter.
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(200, json=make_response([0, MEANINGFUL_RAIN_MM - 0.1, 0]))
    )
    reading = get_current_conditions(37.77, -122.42)
    assert reading.days_since_meaningful_rain == float(LOOKBACK_DAYS)


@respx.mock
def test_http_error_raises_weather_fetch_error():
    respx.get(BASE_URL).mock(return_value=httpx.Response(500))
    try:
        get_current_conditions(37.77, -122.42)
        assert False, "expected WeatherFetchError"
    except WeatherFetchError:
        pass


def test_days_since_meaningful_rain_unit():
    assert _days_since_meaningful_rain([0, 0, 5.0, 0], meaningful_rain_mm=2.5, lookback_days=21) == 1.0
    assert _days_since_meaningful_rain([5.0, 0, 0, 0], meaningful_rain_mm=2.5, lookback_days=21) == 3.0
    assert _days_since_meaningful_rain([0, 0, 0, 0], meaningful_rain_mm=2.5, lookback_days=21) == 21.0


def test_lookback_window_matches_normalization_range_in_config():
    """Regression test for the bug found during the reliability audit: the
    precip lookback window and the days_since_rain normalization range must
    match exactly, or the factor silently caps below full contribution."""
    normalization_range = CONFIG["factors"]["days_since_rain"]["range"]
    assert normalization_range[1] == float(LOOKBACK_DAYS)
