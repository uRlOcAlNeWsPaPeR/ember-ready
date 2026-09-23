"""US Census Bureau ZCTA (ZIP Code Tabulation Area) Gazetteer lookup.

This is the authoritative source for "ZIP-centroid" results — a bare ZIP
code query resolves here first, NOT through a third-party geocoder's
fuzzy place-name match. The centroid is a true INTPTLAT/INTPTLONG from
Census's own gazetteer file (see scripts/fetch_zip_centroids.py), but it
still only approximates a whole ZCTA area — often many square miles — so
callers must label it as ZIP-centroid precision, never property-level.
"""
from __future__ import annotations

import csv
import functools
import re
from pathlib import Path

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "zcta_centroids.csv"

SOURCE = "US Census Bureau ZCTA Gazetteer (2024)"

ZIP_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")


class ZctaLookupError(Exception):
    pass


def is_zip_query(query: str) -> bool:
    return bool(ZIP_PATTERN.match(query.strip()))


def _extract_zip5(query: str) -> str:
    return query.strip()[:5]


@functools.lru_cache(maxsize=1)
def _load_table(csv_path: str) -> dict[str, tuple[float, float]]:
    table: dict[str, tuple[float, float]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table[row["zip"]] = (float(row["latitude"]), float(row["longitude"]))
    return table


def get_zip_centroid(query: str, csv_path: Path | None = None) -> tuple[float, float]:
    """Returns (latitude, longitude) for a 5-digit ZIP (a ZIP+4 has its
    +4 suffix ignored — ZCTAs are defined at the 5-digit level)."""
    zip5 = _extract_zip5(query)
    path = csv_path or DEFAULT_CSV_PATH
    table = _load_table(str(path))

    coords = table.get(zip5)
    if coords is None:
        raise ZctaLookupError(f"ZIP {zip5!r} not found in Census ZCTA gazetteer")
    return coords
