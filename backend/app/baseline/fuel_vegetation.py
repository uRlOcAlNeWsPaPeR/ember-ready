"""LANDFIRE fuel model (FBFM40) live point query.

LANDFIRE publishes CONUS-wide 30m fuel model rasters through a public
GeoServer WMS. Rather than downloading and clipping multi-GB rasters, we
query the pixel value at a single point live via WMS GetFeatureInfo — this
is a real, free, unauthenticated, per-request call against LANDFIRE's own
hosted 2023 CONUS layer.

IMPORTANT: `FBFM40_HAZARD_SCORE` below is EmberReady's own simplified,
manually-assigned 0-1 proxy for "how fire-conducive is this fuel type",
grouped from the standard Scott & Burgan (2005) 40 fuel model catalog. It is
NOT an official LANDFIRE hazard rating and NOT a fire behavior model output
(rate of spread, flame length, etc. require a real fire behavior model such
as FlamMap/FARSITE with weather + terrain inputs, which is out of scope for
this scorer). It exists only to give a transparent, explainable 0-1
ingredient for the weighted score, and is clearly labeled as a proxy in the
API response.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.schemas import Resolution

WMS_URL = "https://edcintl.cr.usgs.gov/geoserver/landfire/wms"
LAYER_NAME = "LF2023_FBFM40_CONUS"
VINTAGE = "LANDFIRE 2023 (LF2023) FBFM40, CONUS"
TIMEOUT = 10.0

FUEL_SOURCE = "LANDFIRE FBFM40 (live WMS GetFeatureInfo pixel query)"
FUEL_RESOLUTION = Resolution.GRIDDED_30M

# code -> (label, hazard_score 0-1)
FBFM40_HAZARD_SCORE: dict[int, tuple[str, float]] = {
    91: ("NB1 Urban/Developed", 0.0),
    92: ("NB2 Snow/Ice", 0.0),
    93: ("NB3 Agricultural", 0.05),
    98: ("NB8 Open Water", 0.0),
    99: ("NB9 Bare Ground", 0.0),
    101: ("GR1 Short sparse dry grass", 0.40),
    102: ("GR2 Low load dry grass", 0.45),
    103: ("GR3 Low load very coarse humid grass", 0.45),
    104: ("GR4 Moderate load dry grass", 0.50),
    105: ("GR5 Low load humid grass", 0.45),
    106: ("GR6 Moderate load humid grass", 0.50),
    107: ("GR7 High load dry grass", 0.60),
    108: ("GR8 High load very coarse humid grass", 0.55),
    109: ("GR9 Very high load humid grass", 0.60),
    121: ("GS1 Low load dry grass-shrub", 0.45),
    122: ("GS2 Moderate load dry grass-shrub", 0.55),
    123: ("GS3 Moderate load humid grass-shrub", 0.55),
    124: ("GS4 High load humid grass-shrub", 0.65),
    141: ("SH1 Low load dry shrub", 0.55),
    142: ("SH2 Moderate load dry shrub", 0.65),
    143: ("SH3 Moderate load humid shrub", 0.60),
    144: ("SH4 Low load humid timber-shrub", 0.55),
    145: ("SH5 High load dry shrub", 0.80),
    146: ("SH6 Low load humid shrub", 0.60),
    147: ("SH7 Very high load dry shrub", 0.85),
    148: ("SH8 High load humid shrub", 0.70),
    149: ("SH9 Very high load humid shrub", 0.80),
    161: ("TU1 Light load dry timber-grass-shrub", 0.45),
    162: ("TU2 Moderate load humid timber-shrub", 0.50),
    163: ("TU3 Moderate load humid timber-grass-shrub", 0.55),
    164: ("TU4 Dwarf conifer with understory", 0.60),
    165: ("TU5 Very high load dry timber-shrub", 0.70),
    181: ("TL1 Low load compact conifer litter", 0.30),
    182: ("TL2 Low load broadleaf litter", 0.30),
    183: ("TL3 Moderate load conifer litter", 0.40),
    184: ("TL4 Small downed logs", 0.40),
    185: ("TL5 High load conifer litter", 0.50),
    186: ("TL6 High load broadleaf litter", 0.45),
    187: ("TL7 Large downed logs", 0.45),
    188: ("TL8 Long-needle litter", 0.50),
    189: ("TL9 Very high load broadleaf litter", 0.60),
    201: ("SB1 Low load activity fuel", 0.55),
    202: ("SB2 Moderate load activity/low load blowdown", 0.70),
    203: ("SB3 High load activity fuel/moderate blowdown", 0.85),
    204: ("SB4 High load blowdown", 0.95),
}

DEFAULT_HAZARD_SCORE = 0.35  # used only if a returned code isn't in our lookup


class FuelFetchError(Exception):
    pass


@dataclass
class FuelReading:
    fbfm40_code: int
    label: str
    hazard_score: float
    observed_at: datetime
    source: str = FUEL_SOURCE
    resolution: Resolution = FUEL_RESOLUTION
    vintage: str = VINTAGE


def get_fuel_model(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> FuelReading:
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)

    # A tiny bbox (~0.02 deg) around the point with the query pixel at its center.
    delta = 0.01
    bbox = f"{longitude - delta},{latitude - delta},{longitude + delta},{latitude + delta}"

    try:
        resp = client.get(
            WMS_URL,
            params={
                "service": "WMS",
                "version": "1.1.1",
                "request": "GetFeatureInfo",
                "layers": LAYER_NAME,
                "query_layers": LAYER_NAME,
                "bbox": bbox,
                "width": 101,
                "height": 101,
                "x": 50,
                "y": 50,
                "srs": "EPSG:4326",
                "info_format": "application/json",
                "feature_count": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise FuelFetchError(f"LANDFIRE WMS request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    features = data.get("features") or []
    if not features:
        raise FuelFetchError(f"No LANDFIRE pixel returned for ({latitude}, {longitude})")

    try:
        code = int(features[0]["properties"]["GRAY_INDEX"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FuelFetchError(f"Unexpected LANDFIRE response shape: {data}") from exc

    label, hazard_score = FBFM40_HAZARD_SCORE.get(code, (f"Unknown FBFM40 code {code}", DEFAULT_HAZARD_SCORE))

    return FuelReading(
        fbfm40_code=code,
        label=label,
        hazard_score=hazard_score,
        observed_at=datetime.now(timezone.utc),
    )
