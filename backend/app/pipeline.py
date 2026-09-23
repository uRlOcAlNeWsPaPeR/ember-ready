"""Orchestrates geocode -> weather + baseline factor fetches -> FeatureSet.

Each factor is fetched independently and failures are caught individually
— one upstream source failing (most often LANDFIRE's public WMS, the least
reliable of the five integrations) must not take down the whole request.
A failure is recorded in FeatureSet.failures with a specific reason, never
silently papered over with a default value; the scorer turns that into an
"unavailable" factor and a reduced confidence rating.

Only geocoding failure is fatal — without a location, nothing else can be
computed.
"""
from __future__ import annotations

import httpx

from app.baseline import elevation_slope, fire_history, fuel_vegetation
from app.geocode import resolver
from app.schemas import (
    BurnProbabilityFactor,
    FactorFailure,
    FeatureSet,
    FuelFactor,
    Location,
    SlopeFactor,
    WeatherFactors,
)
from app.weather import openmeteo


def build_feature_set(query: str, client: httpx.Client | None = None) -> FeatureSet:
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        location = resolver.resolve(query, client=client)
        return build_feature_set_for_location(location, client=client)
    finally:
        if owns_client:
            client.close()


def build_feature_set_for_location(location: Location, client: httpx.Client) -> FeatureSet:
    failures: list[FactorFailure] = []

    weather = None
    try:
        w = openmeteo.get_current_conditions(location.latitude, location.longitude, client=client)
        weather = WeatherFactors(
            temperature_c=w.temperature_c,
            relative_humidity_pct=w.relative_humidity_pct,
            wind_speed_kmh=w.wind_speed_kmh,
            wind_gusts_kmh=w.wind_gusts_kmh,
            wind_direction_deg=w.wind_direction_deg,
            days_since_meaningful_rain=w.days_since_meaningful_rain,
            observed_at=w.observed_at,
            source=w.source,
            resolution=w.resolution,
        )
    except openmeteo.WeatherFetchError as exc:
        failures.append(FactorFailure(factor="weather", reason=f"Open-Meteo request failed: {exc}"))

    slope = None
    try:
        s = elevation_slope.get_slope(location.latitude, location.longitude, client=client)
        slope = SlopeFactor(
            slope_pct=s.slope_pct, source=s.source, resolution=s.resolution, observed_at=s.observed_at
        )
    except elevation_slope.ElevationFetchError as exc:
        failures.append(FactorFailure(factor="slope", reason=f"USGS 3DEP request failed: {exc}"))

    fuel = None
    try:
        f = fuel_vegetation.get_fuel_model(location.latitude, location.longitude, client=client)
        fuel = FuelFactor(
            fuel_model_code=f.fbfm40_code,
            fuel_model_label=f.label,
            fuel_hazard_score=f.hazard_score,
            source=f.source,
            resolution=f.resolution,
            observed_at=f.observed_at,
            vintage=f.vintage,
        )
    except fuel_vegetation.FuelFetchError as exc:
        failures.append(FactorFailure(factor="fuel", reason=f"LANDFIRE WMS request failed: {exc}"))

    burn_probability = None
    if not location.county_fips:
        failures.append(
            FactorFailure(
                factor="burn_probability",
                reason="Could not determine a county for this location (reverse geocoding failed or returned no match).",
            )
        )
    else:
        try:
            reading = fire_history.get_burn_probability(location.county_fips)
            burn_probability = BurnProbabilityFactor(
                bp_national_percentile=reading.bp_national_percentile,
                county_name=reading.county_name,
                source=reading.source,
                resolution=reading.resolution,
                vintage=reading.vintage,
            )
        except fire_history.FireHistoryLookupError as exc:
            failures.append(
                FactorFailure(
                    factor="burn_probability",
                    reason=f"No USDA Wildfire Risk to Communities data for {location.county_name or location.county_fips}: {exc}",
                )
            )

    return FeatureSet(
        location=location,
        weather=weather,
        slope=slope,
        fuel=fuel,
        burn_probability=burn_probability,
        failures=failures,
    )
