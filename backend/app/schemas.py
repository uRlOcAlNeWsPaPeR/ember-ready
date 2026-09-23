"""Shared dataclasses passed between geocode, weather, baseline, and scoring modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Resolution(str, Enum):
    """How precise a given data point actually is, for honest UI labeling."""

    POINT = "point"  # address-range interpolated
    ZIP_CENTROID = "zip_centroid"  # true ZCTA centroid, but the ZIP can span many square miles
    NEIGHBORHOOD = "neighborhood"  # small local sample (e.g. slope from nearby points) or place-name centroid
    GRIDDED_30M = "gridded_30m"
    GRIDDED_1_11KM = "gridded_1_11km"
    COUNTY = "county"


class SearchType(str, Enum):
    ADDRESS = "address"  # full street address, resolved via Census (address-range interpolation)
    ZIP = "zip"  # bare 5-digit ZIP, resolved via the Census ZCTA gazetteer centroid
    PLACE = "place"  # city/town name, resolved via Open-Meteo place-name search
    COORDINATES = "coordinates"  # caller supplied lat/lon directly (e.g. a map click)


# Human-readable, UI-facing explanation of what each precision level actually
# means — written so a non-technical reader understands the limitation, not
# just a resolution code.
LOCATION_PRECISION_LABELS: dict[Resolution, str] = {
    Resolution.POINT: "Address-level (interpolated from street address ranges)",
    Resolution.ZIP_CENTROID: "ZIP-code centroid — approximate, NOT property-specific. A ZIP code can span many square miles of varying terrain.",
    Resolution.NEIGHBORHOOD: "Place-name centroid — approximate, not address-specific",
    Resolution.COUNTY: "County-wide",
}


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class Location:
    latitude: float
    longitude: float
    matched_address: str
    resolution: Resolution
    source: str
    search_type: SearchType
    county_fips: str | None = None  # 5-digit FIPS, e.g. "06075"
    county_name: str | None = None
    state: str | None = None

    @property
    def location_precision_label(self) -> str:
        return LOCATION_PRECISION_LABELS.get(self.resolution, self.resolution.value)


@dataclass
class FactorReading:
    """One explainable ingredient of the risk score. `available=False` means
    the underlying source failed or had no data for this location — in that
    case raw_value/normalized_value are None and contribution_points is 0,
    and the factor must still be listed (never silently dropped) so the UI
    can show it as unavailable and explain the impact on the score.
    """

    name: str
    category: str  # "baseline_wildfire_exposure" | "current_fire_weather"
    weight_points: float  # max points this factor could contribute
    available: bool
    raw_value: float | None
    raw_unit: str
    normalized_value: float | None  # 0-1, higher = more fire-conducive
    contribution_points: float
    source: str
    resolution: Resolution | None
    observed_at: datetime | None
    vintage: str = ""  # dataset vintage/update date, distinct from observed_at for static sources
    detail: str = ""
    unavailable_reason: str = ""


@dataclass
class WeatherFactors:
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    days_since_meaningful_rain: float
    observed_at: datetime
    source: str
    resolution: Resolution
    wind_direction_deg: float = 0.0  # compass degrees, 0-360; informational only, not scored
    vintage: str = "live observation"


@dataclass
class SlopeFactor:
    slope_pct: float
    source: str
    resolution: Resolution
    observed_at: datetime
    vintage: str = "current"


@dataclass
class FuelFactor:
    fuel_model_code: int
    fuel_model_label: str
    fuel_hazard_score: float
    source: str
    resolution: Resolution
    observed_at: datetime
    vintage: str


@dataclass
class BurnProbabilityFactor:
    bp_national_percentile: float
    county_name: str
    source: str
    resolution: Resolution
    vintage: str


@dataclass
class FactorFailure:
    factor: str
    reason: str


@dataclass
class FeatureSet:
    """All raw inputs the scorer needs. Each sub-object is None if that
    source failed or had no data — the scorer must treat that as "exclude
    and explain," never substitute a default.
    """

    location: Location
    weather: WeatherFactors | None
    slope: SlopeFactor | None
    fuel: FuelFactor | None
    burn_probability: BurnProbabilityFactor | None
    failures: list[FactorFailure] = field(default_factory=list)


@dataclass
class ComponentScore:
    """One of the two separated risk concepts (baseline exposure or current
    fire weather), or the combined preparedness indicator."""

    score: float | None  # 0-100, or None if this component couldn't be computed at all
    label: str | None
    available_weight_pct: float  # how much of this component's weight was actually computable


@dataclass
class DataQuality:
    confidence: Confidence
    factors_available: int
    factors_total: int
    unavailable_factors: list[FactorFailure]
    fallback_used: bool
    fallback_detail: str = ""


@dataclass
class ScoreResult:
    baseline_wildfire_exposure: ComponentScore
    current_fire_weather: ComponentScore
    preparedness_indicator: ComponentScore
    factors: list[FactorReading] = field(default_factory=list)
    data_quality: DataQuality | None = None
    model_name: str = "weighted-v2"


class Ownership(str, Enum):
    OWN = "own"
    RENT = "rent"


class ConstructionType(str, Enum):
    WOOD_SIDING_OR_SHAKE_ROOF = "wood_siding_or_shake_roof"
    STUCCO_OR_MASONRY = "stucco_or_masonry"
    MOBILE_OR_MANUFACTURED = "mobile_or_manufactured"
    OTHER_OR_UNKNOWN = "other_or_unknown"


@dataclass
class HouseholdProfile:
    ownership: Ownership
    has_pets: bool
    mobility_needs: bool
    construction_type: ConstructionType


@dataclass
class ChecklistItem:
    text: str
    reasons: list[str]  # which inputs triggered this item, e.g. ["everyone"], ["renter"], ["pet_owner"]


@dataclass
class ChecklistResult:
    defensible_space: list[ChecklistItem]
    go_bag: list[ChecklistItem]
    evacuation_route: list[ChecklistItem]
    note: str
