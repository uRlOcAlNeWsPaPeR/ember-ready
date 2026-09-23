"""Data prep: build a lightweight US state-boundary outline GeoJSON for the
Earthquake Risk map, so state lines are clearly visible over the terrain
basemap + seismic hazard grid (OpenTopoMap's own tile rendering doesn't
draw prominent US state boundaries at national zoom).

Same US Census Bureau cartographic boundary source and pattern as
build_county_map_data.py, just at the state level — only ~52 features
(50 states + DC + Puerto Rico), so no coordinate rounding or size
optimization is needed the way the ~3200-county file requires.

Run with: python -m scripts.build_state_boundaries
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx
import shapefile

CENSUS_SHAPEFILE_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip"
SHAPEFILE_BASENAME = "cb_2023_us_state_20m"

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "map" / "us_states.geojson"


def main() -> None:
    print(f"Downloading {CENSUS_SHAPEFILE_URL} ...")
    resp = httpx.get(CENSUS_SHAPEFILE_URL, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        shp = io.BytesIO(zf.read(f"{SHAPEFILE_BASENAME}.shp"))
        dbf = io.BytesIO(zf.read(f"{SHAPEFILE_BASENAME}.dbf"))
        sf = shapefile.Reader(shp=shp, dbf=dbf)

        features = []
        for shape_record in sf.iterShapeRecords():
            rec = shape_record.record
            geometry = shape_record.shape.__geo_interface__
            features.append(
                {
                    "type": "Feature",
                    "properties": {"name": rec["NAME"], "stusps": rec["STUSPS"]},
                    "geometry": geometry,
                }
            )

    feature_collection = {
        "type": "FeatureCollection",
        "properties": {
            "boundaries_source": "US Census Bureau Cartographic Boundary Files, 2023, states, 20m generalization"
        },
        "features": features,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, separators=(",", ":"))

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"Wrote {len(features)} states to {OUTPUT_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
