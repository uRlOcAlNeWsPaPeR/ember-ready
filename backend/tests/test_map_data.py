"""Validates the committed static map file itself — catches a bad
regeneration (missing join, wrong FIPS padding, corrupt geometry) without
needing network access.
"""
import json

from app.api.map import MAP_DATA_PATH

VALID_CATEGORIES = {"Low", "Moderate", "High", "Extreme", "No data"}


def load():
    with MAP_DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_file_exists_and_parses():
    data = load()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 3000  # ~3,143 US counties + territories


def test_top_level_source_attribution_present():
    data = load()
    props = data["properties"]
    assert "Census" in props["boundaries_source"]
    assert "Wildfire Risk to Communities" in props["hazard_source"]
    assert props["hazard_vintage"]


def test_every_feature_has_required_properties():
    data = load()
    seen_fips = set()
    for feature in data["features"]:
        props = feature["properties"]
        assert props["fips"] and len(props["fips"]) == 5
        assert props["name"]
        assert props["category"] in VALID_CATEGORIES
        assert isinstance(props["has_data"], bool)
        if props["has_data"]:
            assert props["bp_national_percentile"] is not None
            assert 0.0 <= props["bp_national_percentile"] <= 1.0
        else:
            assert props["category"] == "No data"
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        seen_fips.add(props["fips"])

    assert len(seen_fips) == len(data["features"])  # no duplicate counties


def test_known_counties_have_expected_categories():
    data = load()
    by_fips = {f["properties"]["fips"]: f["properties"] for f in data["features"]}

    butte_ca = by_fips["06007"]
    assert butte_ca["category"] == "Extreme"
    assert butte_ca["bp_national_percentile"] > 0.75

    assert by_fips["06075"]["category"] in {"Moderate", "High"}


def test_category_distribution_is_not_degenerate():
    """A bug that collapses everything into one bucket would sail through
    the per-feature checks above but produce a useless map."""
    data = load()
    from collections import Counter

    counts = Counter(f["properties"]["category"] for f in data["features"])
    real_buckets = {k: v for k, v in counts.items() if k != "No data"}
    assert len(real_buckets) == 4
    assert min(real_buckets.values()) > 100
