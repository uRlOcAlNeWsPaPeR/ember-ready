"""One-time data prep: download USDA Forest Service Wildfire Risk to
Communities' county-level summary workbook and extract a small CSV of just
the fields EmberReady needs (county FIPS + national burn-probability /
risk-to-structures percentiles).

This is the only "static baseline" source that needs a bulk download —
LANDFIRE fuel data is queried live per-request via WMS (see
app/baseline/fuel_vegetation.py). The WRC workbook itself does not expose a
live per-point API (see the source-verification memo), but is small enough
(~5MB) to download once and ship as a ~200KB derived CSV.

Run with: python -m scripts.fetch_static_layers
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
import openpyxl

WRC_WORKBOOK_URL = "https://wildfirerisk.org/wp-content/uploads/2026/04/wrc_download_20260415.xlsx"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "wrc_counties.csv"

SOURCE_CITATION = (
    "USDA Forest Service. 2026. Wildfire Risk to Communities. "
    "https://wildfirerisk.org [Accessed via bulk county-level download, 2026-04-15 vintage]"
)


def main() -> None:
    print(f"Downloading {WRC_WORKBOOK_URL} ...")
    resp = httpx.get(WRC_WORKBOOK_URL, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()

    wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
    ws = wb["Counties"]

    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    col = {name: i for i, name in enumerate(header)}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "county_fips",
                "county_name",
                "state_name",
                "total_buildings",
                "bp_national_percentile",
                "risk_national_percentile",
            ]
        )
        count = 0
        for row in rows:
            if row[col["GEOID"]] is None:
                continue
            county_fips = str(row[col["GEOID"]]).zfill(5)
            writer.writerow(
                [
                    county_fips,
                    row[col["NAME"]],
                    row[col["STATE_NAME"]],
                    row[col["TOTAL_BUILDINGS"]],
                    row[col["BP_NATIONAL_RANK"]],
                    row[col["RISK_NATIONAL_RANK"]],
                ]
            )
            count += 1

    print(f"Wrote {count} counties to {OUTPUT_PATH}")
    print(f"Citation: {SOURCE_CITATION}")


if __name__ == "__main__":
    main()
