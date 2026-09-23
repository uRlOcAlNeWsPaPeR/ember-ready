from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.api.response_models import (
    ComponentScoreOut,
    DataQualityOut,
    FactorOut,
    LocationOut,
    ScoreResponse,
    UnavailableFactorOut,
)
from app.cache import db as cache_db
from app.geocode import census
from app.geocode.resolver import GeocodeError
from app.pipeline import build_feature_set, build_feature_set_for_location
from app.schemas import FeatureSet, Location, Resolution, ScoreResult, SearchType
from app.scoring.weighted_model import WeightedRiskModel

router = APIRouter()
_model = WeightedRiskModel()

CACHE_TTL_SECONDS = 600


def _location_from_coords(latitude: float, longitude: float, client: httpx.Client) -> Location:
    """Build a Location for map-click coordinates, best-effort reverse
    geocoding the county via Census so the burn-probability factor can
    still be looked up (see resolver.py for the same pattern)."""
    county_info: dict = {}
    try:
        county_info = census.reverse_geocode_county(latitude, longitude, client=client)
    except httpx.HTTPError:
        pass

    return Location(
        latitude=latitude,
        longitude=longitude,
        matched_address=f"{latitude:.4f}, {longitude:.4f}",
        resolution=Resolution.POINT,
        source="User-provided coordinates (map click)",
        search_type=SearchType.COORDINATES,
        county_fips=county_info.get("county_fips"),
        county_name=county_info.get("county_name"),
        state=county_info.get("state"),
    )


def _component_out(component) -> ComponentScoreOut:
    return ComponentScoreOut(
        score=component.score, label=component.label, available_weight_pct=component.available_weight_pct
    )


def _to_response(query: str, features: FeatureSet, result: ScoreResult, cached: bool = False) -> ScoreResponse:
    location = LocationOut(
        latitude=features.location.latitude,
        longitude=features.location.longitude,
        matched_address=features.location.matched_address,
        search_type=features.location.search_type.value,
        location_precision=features.location.resolution.value,
        location_precision_label=features.location.location_precision_label,
        source=features.location.source,
        county_fips=features.location.county_fips,
        county_name=features.location.county_name,
        state=features.location.state,
    )
    factors = [
        FactorOut(
            name=f.name,
            category=f.category,
            weight_points=f.weight_points,
            available=f.available,
            raw_value=f.raw_value,
            raw_unit=f.raw_unit,
            normalized_value=f.normalized_value,
            contribution_points=f.contribution_points,
            source=f.source,
            resolution=f.resolution.value if f.resolution else None,
            observed_at=f.observed_at.isoformat() if f.observed_at else None,
            vintage=f.vintage,
            detail=f.detail,
            unavailable_reason=f.unavailable_reason,
        )
        for f in result.factors
    ]

    weight_by_name = {f.name: f.weight_points for f in result.factors}
    dq = result.data_quality
    data_quality = DataQualityOut(
        confidence=dq.confidence.value,
        factors_available=dq.factors_available,
        factors_total=dq.factors_total,
        unavailable_factors=[
            UnavailableFactorOut(
                factor=uf.factor, reason=uf.reason, weight_excluded=weight_by_name.get(uf.factor, 0.0)
            )
            for uf in dq.unavailable_factors
        ],
        fallback_used=dq.fallback_used,
        fallback_detail=dq.fallback_detail,
    )

    return ScoreResponse(
        query=query,
        search_type=features.location.search_type.value,
        location=location,
        baseline_wildfire_exposure=_component_out(result.baseline_wildfire_exposure),
        current_fire_weather=_component_out(result.current_fire_weather),
        preparedness_indicator=_component_out(result.preparedness_indicator),
        factors=factors,
        data_quality=data_quality,
        model_name=result.model_name,
        wind_speed_kmh=features.weather.wind_speed_kmh if features.weather else None,
        wind_gusts_kmh=features.weather.wind_gusts_kmh if features.weather else None,
        wind_direction_deg=features.weather.wind_direction_deg if features.weather else None,
        cached=cached,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/score", response_model=ScoreResponse)
def get_score(
    query: Optional[str] = Query(
        None, min_length=2, max_length=200, description="US street address or ZIP code"
    ),
    lat: Optional[float] = Query(
        None, ge=-90, le=90, description="Latitude — alternative to `query`, e.g. from a map click"
    ),
    lon: Optional[float] = Query(
        None, ge=-180, le=180, description="Longitude — required together with `lat`"
    ),
    use_cache: bool = Query(True, description="Serve/store a cached response (10 min TTL)"),
) -> ScoreResponse:
    has_query = query is not None
    has_coords = lat is not None and lon is not None
    if has_query == has_coords:  # neither, or both — exactly one is required
        raise HTTPException(
            status_code=400,
            detail="Provide either 'query' (address/ZIP) or both 'lat' and 'lon', not neither or both.",
        )

    cache_key = query if has_query else f"latlon:{lat:.4f},{lon:.4f}"

    if use_cache:
        cached_payload = cache_db.get_cached(cache_key)
        if cached_payload is not None:
            cached_payload["cached"] = True
            return ScoreResponse(**cached_payload)

    try:
        with httpx.Client(timeout=15.0) as client:
            if has_query:
                features = build_feature_set(query, client=client)
            else:
                location = _location_from_coords(lat, lon, client)
                features = build_feature_set_for_location(location, client=client)
    except GeocodeError as exc:
        raise HTTPException(status_code=404, detail=f"Could not resolve location: {exc}") from exc

    result = _model.score(features)
    response = _to_response(cache_key, features, result, cached=False)

    if use_cache:
        cache_db.set_cached(cache_key, response.model_dump(mode="json"), ttl_seconds=CACHE_TTL_SECONDS)

    return response
