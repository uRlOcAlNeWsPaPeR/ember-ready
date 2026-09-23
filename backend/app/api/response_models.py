"""Pydantic response models for the public API — kept separate from the
internal dataclasses in app/schemas.py so the wire format can stay stable
even if internal representations change (e.g. when a future sklearn model
is swapped in behind scoring/model_interface.py)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

US_ONLY_NOTICE = (
    "EmberReady covers the United States only. Addresses and ZIP codes outside the US "
    "are not supported in this MVP."
)

DISCLAIMER = (
    "EmberReady is an educational wildfire-preparedness tool, not an emergency alert system "
    "and not an official fire-risk determination. It combines current weather with modeled, "
    "county- and grid-scale baseline data — it cannot see your specific property. For active "
    "incidents, evacuation orders, and real-time updates, always consult local fire authorities, "
    "Watch Duty, and other official emergency sources."
)

SAFETY_NOTICE = (
    "EmberReady is an educational preparedness tool. It is not an official wildfire forecast, "
    "evacuation notice, or emergency alert. Follow local fire authorities and official emergency "
    "guidance."
)


class LocationOut(BaseModel):
    latitude: float
    longitude: float
    matched_address: str
    search_type: str
    location_precision: str
    location_precision_label: str
    source: str
    county_fips: Optional[str] = None
    county_name: Optional[str] = None
    state: Optional[str] = None


class FactorOut(BaseModel):
    name: str
    category: str
    weight_points: float
    available: bool
    raw_value: Optional[float] = None
    raw_unit: str
    normalized_value: Optional[float] = None
    contribution_points: float
    source: str
    resolution: Optional[str] = None
    observed_at: Optional[str] = None
    vintage: str = ""
    detail: str = ""
    unavailable_reason: str = ""


class ComponentScoreOut(BaseModel):
    score: Optional[float] = None
    label: Optional[str] = None
    available_weight_pct: float


class UnavailableFactorOut(BaseModel):
    factor: str
    reason: str
    weight_excluded: float


class DataQualityOut(BaseModel):
    confidence: str
    factors_available: int
    factors_total: int
    unavailable_factors: List[UnavailableFactorOut]
    fallback_used: bool
    fallback_detail: str = ""


class ScoreResponse(BaseModel):
    query: str
    search_type: str
    location: LocationOut
    baseline_wildfire_exposure: ComponentScoreOut
    current_fire_weather: ComponentScoreOut
    preparedness_indicator: ComponentScoreOut
    factors: List[FactorOut]
    data_quality: DataQualityOut
    model_name: str
    wind_speed_kmh: Optional[float] = None
    wind_gusts_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    safety_notice: str = SAFETY_NOTICE
    disclaimer: str = DISCLAIMER
    us_only_notice: str = US_ONLY_NOTICE
    cached: bool = False
    generated_at: str
