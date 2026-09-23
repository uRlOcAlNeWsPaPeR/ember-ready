"""County-level long-term wildfire-likelihood baseline, from USDA Forest
Service Wildfire Risk to Communities (WRC).

WRC does not expose a live per-point API (verified during source review —
see the project decision memo). Its data is distributed as bulk downloads,
so we ship a small pre-extracted CSV (`data/wrc_counties.csv`, produced by
scripts/fetch_static_layers.py) with the national burn-probability
percentile per county. This is a MODELED long-term simulation output
(USFS's FSim burn-probability model), not an observed historical fire
record, and it is county-scale, not address-level — both facts must be
surfaced in the UI, not just this docstring.
"""
from __future__ import annotations

import csv
import functools
from dataclasses import dataclass
from pathlib import Path

from app.schemas import Resolution

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wrc_counties.csv"

FIRE_HISTORY_SOURCE = (
    "USDA Forest Service Wildfire Risk to Communities — county-level burn probability "
    "national percentile (FSim-modeled, not observed fire history)"
)
FIRE_HISTORY_RESOLUTION = Resolution.COUNTY
FIRE_HISTORY_VINTAGE = "WRC county download, 2026-04-15 vintage"


@dataclass
class FireHistoryReading:
    county_fips: str
    county_name: str
    bp_national_percentile: float  # 0-1
    source: str = FIRE_HISTORY_SOURCE
    resolution: Resolution = FIRE_HISTORY_RESOLUTION
    vintage: str = FIRE_HISTORY_VINTAGE


class FireHistoryLookupError(Exception):
    pass


@functools.lru_cache(maxsize=1)
def _load_table(csv_path: str) -> dict[str, dict]:
    table: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table[row["county_fips"]] = row
    return table


def get_burn_probability(county_fips: str, csv_path: Path | None = None) -> FireHistoryReading:
    if not county_fips:
        raise FireHistoryLookupError("No county FIPS provided")

    path = csv_path or DEFAULT_CSV_PATH
    table = _load_table(str(path))
    row = table.get(county_fips)
    if row is None:
        raise FireHistoryLookupError(f"County FIPS {county_fips!r} not found in WRC table")

    bp = row["bp_national_percentile"]
    if bp in (None, ""):
        raise FireHistoryLookupError(f"County FIPS {county_fips!r} has insufficient WRC data")

    return FireHistoryReading(
        county_fips=county_fips,
        county_name=row["county_name"],
        bp_national_percentile=float(bp),
    )
