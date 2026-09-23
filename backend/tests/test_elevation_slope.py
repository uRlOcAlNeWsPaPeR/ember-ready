import httpx
import respx

from app.baseline.elevation_slope import BASE_URL, ElevationFetchError, get_elevation_m, get_slope


def epqs_response(value):
    return httpx.Response(200, json={"value": str(value)})


@respx.mock
def test_flat_terrain_has_near_zero_slope():
    # center, north, south, east, west all at the same elevation
    respx.get(BASE_URL).mock(return_value=epqs_response(100.0))
    reading = get_slope(37.0, -122.0)
    assert reading.slope_pct == 0.0
    assert reading.center_elevation_m == 100.0


@respx.mock
def test_steep_terrain_has_high_slope():
    # 90m north-south rise of 90m over ~180m horizontal run => 50% slope on that axis
    route = respx.get(BASE_URL)
    elevations = iter([100.0, 190.0, 100.0, 100.0, 100.0])  # center, north, south, east, west

    def responder(request):
        return epqs_response(next(elevations))

    route.mock(side_effect=responder)
    reading = get_slope(37.0, -122.0)
    assert reading.slope_pct > 20.0


@respx.mock
def test_elevation_fetch_error_on_bad_payload():
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json={"unexpected": "shape"}))
    try:
        get_elevation_m(37.0, -122.0, httpx.Client())
        assert False, "expected ElevationFetchError"
    except ElevationFetchError:
        pass
