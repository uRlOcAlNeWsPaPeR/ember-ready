"""One-time data prep: download the US Census Bureau's official ZCTA
(ZIP Code Tabulation Area) Gazetteer file and extract a small CSV of
ZIP -> true centroid (INTPTLAT/INTPTLONG), so a bare-ZIP search resolves
against authoritative Census data instead of a third-party geocoder's
fuzzy place-name match.

Run with: python -m scripts.fetch_zip_centroids
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import httpx

GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip"
SOURCE_FILENAME = "2024_Gaz_zcta_national.txt"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "zcta_centroids.csv"

SOURCE_CITATION = "US Census Bureau, 2024 Gazetteer Files (ZCTA National), INTPTLAT/INTPTLONG"


def main() -> None:
    print(f"Downloading {GAZETTEER_URL} ...")
    resp = httpx.get(GAZETTEER_URL, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        raw = zf.read(SOURCE_FILENAME).decode("latin-1")

    lines = raw.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    idx = {name: i for i, name in enumerate(header)}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["zip", "latitude", "longitude"])
        for line in lines[1:]:
            if not line.strip():
                continue
            cols = line.split("\t")
            zip_code = cols[idx["GEOID"]].strip()
            lat = cols[idx["INTPTLAT"]].strip()
            lon = cols[idx["INTPTLONG"]].strip()
            if not zip_code or not lat or not lon:
                continue
            writer.writerow([zip_code, lat, lon])
            count += 1

    print(f"Wrote {count} ZCTA centroids to {OUTPUT_PATH}")
    print(f"Citation: {SOURCE_CITATION}")


if __name__ == "__main__":
    main()
