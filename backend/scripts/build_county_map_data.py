"""One-time data prep: build the static county-choropleth GeoJSON for the
national baseline hazard map.

Downloads the US Census Bureau's 2023 cartographic boundary county
shapefile (20m generalization — appropriately coarse for a national-zoom
choropleth, ~900KB zipped), converts it to GeoJSON with pyshp (no GDAL
system dependency needed), and joins each county's baseline hazard bucket
from the already-committed WRC county CSV (see fetch_static_layers.py).

Category thresholds are imported from the live scorer's own label
thresholds, so the map legend can never silently drift out of sync with
the Low/Moderate/High/Extreme meaning used everywhere else in the app.

Run with: python -m scripts.build_county_map_data
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import httpx
import shapefile

from app.scoring.config import load_weights_config
from app.scoring.weighted_model import _label_for

CENSUS_SHAPEFILE_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip"
SHAPEFILE_BASENAME = "cb_2023_us_county_20m"

WRC_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "wrc_counties.csv"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "map" / "us_counties.geojson"

# Coordinates are already generalized (20m); rounding to 5 decimal places
# (~1.1m) trims file size further with no visible quality loss at national
# or state zoom levels.
COORD_PRECISION = 5

SOURCE_CITATION = {
    "boundaries_source": "US Census Bureau Cartographic Boundary Files, 2023, counties, 20m generalization",
    "hazard_source": "USDA Forest Service Wildfire Risk to Communities (county-level, FSim-modeled burn probability national percentile)",
    "hazard_vintage": "2026-04-15",
}


def _round_coords(coords):
    if isinstance(coords[0], (int, float)):
        return [round(c, COORD_PRECISION) for c in coords]
    return [_round_coords(c) for c in coords]


def _load_wrc_table() -> dict[str, dict]:
    table = {}
    with WRC_CSV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table[row["county_fips"]] = row
    return table


def main() -> None:
    print(f"Downloading {CENSUS_SHAPEFILE_URL} ...")
    resp = httpx.get(CENSUS_SHAPEFILE_URL, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        shp = io.BytesIO(zf.read(f"{SHAPEFILE_BASENAME}.shp"))
        dbf = io.BytesIO(zf.read(f"{SHAPEFILE_BASENAME}.dbf"))
        sf = shapefile.Reader(shp=shp, dbf=dbf)

        wrc_table = _load_wrc_table()
        scoring_config = load_weights_config()

        features = []
        matched = 0
        no_data = 0

        for shape_record in sf.iterShapeRecords():
            rec = shape_record.record
            fips = rec["GEOID"]
            wrc_row = wrc_table.get(fips)

            geometry = shape_record.shape.__geo_interface__
            geometry = {
                "type": geometry["type"],
                "coordinates": _round_coords(geometry["coordinates"]),
            }

            if wrc_row and wrc_row["bp_national_percentile"] not in (None, ""):
                bp = float(wrc_row["bp_national_percentile"])
                category = _label_for(bp * 100, scoring_config)
                name = wrc_row["county_name"]
                has_data = True
                matched += 1
            else:
                bp = None
                category = "No data"
                name = f"{rec['NAMELSAD']}, {rec['STUSPS']}"
                has_data = False
                no_data += 1

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "fips": fips,
                        "name": name,
                        "state": rec["STUSPS"],
                        "bp_national_percentile": bp,
                        "category": category,
                        "has_data": has_data,
                    },
                    "geometry": geometry,
                }
            )

    feature_collection = {
        "type": "FeatureCollection",
        "properties": SOURCE_CITATION,
        "features": features,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, separators=(",", ":"))

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"Wrote {len(features)} counties ({matched} with hazard data, {no_data} without) to {OUTPUT_PATH}")
    print(f"File size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
