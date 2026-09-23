import pytest

from app.baseline.fire_history import FireHistoryLookupError, get_burn_probability


def test_known_county_returns_percentile():
    # Autauga County, AL — verified present in the committed WRC extract.
    reading = get_burn_probability("01001")
    assert reading.county_name == "Autauga County, AL"
    assert 0.0 <= reading.bp_national_percentile <= 1.0


def test_unknown_county_raises():
    with pytest.raises(FireHistoryLookupError):
        get_burn_probability("99999")


def test_empty_fips_raises():
    with pytest.raises(FireHistoryLookupError):
        get_burn_probability("")
