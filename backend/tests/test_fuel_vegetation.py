import httpx
import respx

from app.baseline.fuel_vegetation import (
    DEFAULT_HAZARD_SCORE,
    WMS_URL,
    FuelFetchError,
    get_fuel_model,
)


def wms_response(gray_index):
    return httpx.Response(
        200,
        json={
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"GRAY_INDEX": gray_index}}],
        },
    )


@respx.mock
def test_known_fuel_code_returns_labeled_hazard():
    respx.get(WMS_URL).mock(return_value=wms_response(145))
    reading = get_fuel_model(39.76, -121.62)
    assert reading.fbfm40_code == 145
    assert "SH5" in reading.label
    assert reading.hazard_score == 0.80


@respx.mock
def test_non_burnable_code_has_zero_hazard():
    respx.get(WMS_URL).mock(return_value=wms_response(91))
    reading = get_fuel_model(39.76, -121.62)
    assert reading.hazard_score == 0.0


@respx.mock
def test_unknown_code_falls_back_to_default():
    respx.get(WMS_URL).mock(return_value=wms_response(999))
    reading = get_fuel_model(39.76, -121.62)
    assert reading.hazard_score == DEFAULT_HAZARD_SCORE


@respx.mock
def test_no_features_raises_fuel_fetch_error():
    respx.get(WMS_URL).mock(return_value=httpx.Response(200, json={"features": []}))
    try:
        get_fuel_model(39.76, -121.62)
        assert False, "expected FuelFetchError"
    except FuelFetchError:
        pass
