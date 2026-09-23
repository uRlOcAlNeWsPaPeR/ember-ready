"""v2 transparent weighted scoring model.

This is a hand-weighted formula, NOT machine learning. Weights, ranges, and
rationale live in weights.json (app/scoring/config.py loads it) rather than
as constants scattered through this file.

Two risk concepts are kept explicitly separate and both returned:
- baseline_wildfire_exposure: long-term regional hazard (burn probability,
  fuel, slope) — 65% of the combined weight.
- current_fire_weather: short-term conditions (wind, gusts, humidity,
  temperature, dry spell) — 35% of the combined weight.
- preparedness_indicator: the transparent combination of the two. This is
  an educational preparedness indicator, not an official risk prediction.

Missing data is never defaulted. If a source fails, that factor is
excluded, its weight is dropped from the relevant component's denominator
(so the component stays on a comparable 0-100 scale computed only from
what's actually known), and confidence is downgraded. See
schemas.FactorReading.available and DataQuality.
"""
from __future__ import annotations

from app.schemas import (
    ComponentScore,
    Confidence,
    DataQuality,
    FactorFailure,
    FactorReading,
    FeatureSet,
    ScoreResult,
)
from app.scoring.config import category_for_factor, load_weights_config
from app.scoring.model_interface import RiskModel

BASELINE_CATEGORY = "baseline_wildfire_exposure"
WEATHER_CATEGORY = "current_fire_weather"


def _normalize(value: float, low: float, high: float, invert: bool = False) -> float:
    if high == low:
        return 0.0
    frac = (value - low) / (high - low)
    frac = max(0.0, min(1.0, frac))
    return 1.0 - frac if invert else frac


def _label_for(score: float, config: dict) -> str:
    for threshold, label in config["label_thresholds"]:
        if score <= threshold:
            return label
    return config["label_thresholds"][-1][1]


class WeightedRiskModel(RiskModel):
    name = "weighted-v2"

    def __init__(self, config: dict | None = None):
        self.config = config or load_weights_config()

    def score(self, features: FeatureSet) -> ScoreResult:
        factors = self._build_factor_readings(features)

        baseline = self._component_score(factors, BASELINE_CATEGORY)
        weather = self._component_score(factors, WEATHER_CATEGORY)
        preparedness = self._preparedness_indicator(baseline, weather)

        data_quality = self._data_quality(factors, features)

        return ScoreResult(
            baseline_wildfire_exposure=baseline,
            current_fire_weather=weather,
            preparedness_indicator=preparedness,
            factors=factors,
            data_quality=data_quality,
            model_name=self.name,
        )

    # --- factor readings -------------------------------------------------

    def _build_factor_readings(self, features: FeatureSet) -> list[FactorReading]:
        cfg = self.config["factors"]
        readings: list[FactorReading] = []

        def unavailable(name: str, reason: str) -> FactorReading:
            spec = cfg[name]
            return FactorReading(
                name=name,
                category=category_for_factor(name, self.config),
                weight_points=spec["weight_points"],
                available=False,
                raw_value=None,
                raw_unit=spec["unit"],
                normalized_value=None,
                contribution_points=0.0,
                source="",
                resolution=None,
                observed_at=None,
                unavailable_reason=reason,
            )

        def available(name: str, raw: float, source: str, resolution, observed_at, vintage="", detail="") -> FactorReading:
            spec = cfg[name]
            normalized = _normalize(raw, *spec["range"], invert=spec.get("invert", False))
            return FactorReading(
                name=name,
                category=category_for_factor(name, self.config),
                weight_points=spec["weight_points"],
                available=True,
                raw_value=raw,
                raw_unit=spec["unit"],
                normalized_value=normalized,
                contribution_points=normalized * spec["weight_points"],
                source=source,
                resolution=resolution,
                observed_at=observed_at,
                vintage=vintage,
                detail=detail,
            )

        # --- baseline factors ---
        if features.burn_probability is not None:
            bp = features.burn_probability
            readings.append(
                available(
                    "burn_probability",
                    bp.bp_national_percentile,
                    bp.source,
                    bp.resolution,
                    None,
                    vintage=bp.vintage,
                    detail=f"National percentile of USFS-modeled long-term burn probability for {bp.county_name}.",
                )
            )
        else:
            readings.append(unavailable("burn_probability", self._failure_reason(features, "burn_probability")))

        if features.fuel is not None:
            # Special-cased rather than routed through `available()`: the
            # FBFM40 code is a categorical id (e.g. 145), not something to
            # linearly normalize — the 0-1 hazard score is already computed
            # by fuel_vegetation.py's lookup table, so it's used directly
            # while the raw code is kept in raw_value purely for display.
            fuel = features.fuel
            weight = cfg["fuel_hazard"]["weight_points"]
            readings.append(
                FactorReading(
                    name="fuel_hazard",
                    category=category_for_factor("fuel_hazard", self.config),
                    weight_points=weight,
                    available=True,
                    raw_value=float(fuel.fuel_model_code),
                    raw_unit=cfg["fuel_hazard"]["unit"],
                    normalized_value=fuel.fuel_hazard_score,
                    contribution_points=fuel.fuel_hazard_score * weight,
                    source=fuel.source,
                    resolution=fuel.resolution,
                    observed_at=fuel.observed_at,
                    vintage=fuel.vintage,
                    detail=f"Fuel model: {fuel.fuel_model_label} (simplified EmberReady proxy score, not an official LANDFIRE hazard rating).",
                )
            )
        else:
            readings.append(unavailable("fuel_hazard", self._failure_reason(features, "fuel_hazard")))

        if features.slope is not None:
            slope = features.slope
            readings.append(
                available(
                    "slope",
                    slope.slope_pct,
                    slope.source,
                    slope.resolution,
                    slope.observed_at,
                    vintage=slope.vintage,
                    detail="Steeper terrain increases fire spread rate upslope.",
                )
            )
        else:
            readings.append(unavailable("slope", self._failure_reason(features, "slope")))

        # --- weather factors (all five come from one WeatherFactors object) ---
        if features.weather is not None:
            w = features.weather
            readings.append(available("wind_gusts", w.wind_gusts_kmh, w.source, w.resolution, w.observed_at, vintage=w.vintage))
            readings.append(available("wind_speed", w.wind_speed_kmh, w.source, w.resolution, w.observed_at, vintage=w.vintage))
            readings.append(
                available(
                    "relative_humidity",
                    w.relative_humidity_pct,
                    w.source,
                    w.resolution,
                    w.observed_at,
                    vintage=w.vintage,
                    detail="Lower humidity increases risk; normalized inversely.",
                )
            )
            readings.append(available("temperature", w.temperature_c, w.source, w.resolution, w.observed_at, vintage=w.vintage))
            readings.append(
                available(
                    "days_since_rain",
                    w.days_since_meaningful_rain,
                    w.source,
                    w.resolution,
                    w.observed_at,
                    vintage=w.vintage,
                    detail=(
                        f"Days since >={self.config['meaningful_rain_mm']}mm precipitation, "
                        f"capped at {self.config['rain_lookback_days']} (the fetched lookback window)."
                    ),
                )
            )
        else:
            reason = self._failure_reason(features, "weather")
            for name in ("wind_gusts", "wind_speed", "relative_humidity", "temperature", "days_since_rain"):
                readings.append(unavailable(name, reason))

        return readings

    @staticmethod
    def _failure_reason(features: FeatureSet, factor_key: str) -> str:
        source_map = {
            "burn_probability": "burn_probability",
            "fuel_hazard": "fuel",
            "slope": "slope",
            "weather": "weather",
        }
        target = source_map.get(factor_key, factor_key)
        for failure in features.failures:
            if failure.factor == target:
                return failure.reason
        return "No data available for this location."

    # --- component scoring -------------------------------------------------

    def _component_score(self, factors: list[FactorReading], category: str) -> ComponentScore:
        in_category = [f for f in factors if f.category == category]
        available_factors = [f for f in in_category if f.available]

        total_category_weight = sum(f.weight_points for f in in_category)
        available_weight = sum(f.weight_points for f in available_factors)

        if available_weight == 0:
            return ComponentScore(score=None, label=None, available_weight_pct=0.0)

        contribution_sum = sum(f.contribution_points for f in available_factors)
        # Rescale to a 0-100 scale using only the weight that was actually
        # computable, so a missing factor doesn't silently bias the score
        # toward "low risk" just because its contribution was 0.
        score = contribution_sum / available_weight * 100
        score = max(0.0, min(100.0, score))

        return ComponentScore(
            score=round(score, 1),
            label=_label_for(score, self.config),
            available_weight_pct=round(available_weight / total_category_weight * 100, 1),
        )

    def _preparedness_indicator(self, baseline: ComponentScore, weather: ComponentScore) -> ComponentScore:
        categories = self.config["categories"]
        baseline_pct = categories[BASELINE_CATEGORY]["weight_pct"] / 100
        weather_pct = categories[WEATHER_CATEGORY]["weight_pct"] / 100

        if baseline.score is None and weather.score is None:
            return ComponentScore(score=None, label=None, available_weight_pct=0.0)
        if baseline.score is None:
            return ComponentScore(score=weather.score, label=weather.label, available_weight_pct=weather_pct * 100)
        if weather.score is None:
            return ComponentScore(score=baseline.score, label=baseline.label, available_weight_pct=baseline_pct * 100)

        combined = baseline.score * baseline_pct + weather.score * weather_pct
        combined = max(0.0, min(100.0, combined))
        return ComponentScore(score=round(combined, 1), label=_label_for(combined, self.config), available_weight_pct=100.0)

    # --- data quality -------------------------------------------------

    def _data_quality(self, factors: list[FactorReading], features: FeatureSet) -> DataQuality:
        missing = [f for f in factors if not f.available]
        missing_names = {f.name for f in missing}

        baseline_missing_all = all(not f.available for f in factors if f.category == BASELINE_CATEGORY)
        weather_missing_all = all(not f.available for f in factors if f.category == WEATHER_CATEGORY)

        rules = self.config["confidence_rules"]
        if baseline_missing_all or weather_missing_all:
            confidence = Confidence.LOW
        elif len(missing) <= rules["high_max_missing_factors"]:
            confidence = Confidence.HIGH
        elif len(missing) <= rules["medium_max_missing_factors"]:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        fallback_used = features.location.search_type.value == "place" and features.location.resolution.value == "neighborhood"

        return DataQuality(
            confidence=confidence,
            factors_available=len(factors) - len(missing),
            factors_total=len(factors),
            unavailable_factors=[FactorFailure(factor=f.name, reason=f.unavailable_reason) for f in missing],
            fallback_used=fallback_used,
            fallback_detail=(
                "Address/ZIP geocoding fell back from the primary source to a secondary place-name lookup."
                if fallback_used
                else ""
            ),
        )
