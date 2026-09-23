from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.weather.alerts import AlertsFetchError, get_active_alerts

router = APIRouter()


class AlertOut(BaseModel):
    event: str
    headline: str
    severity: str
    urgency: str
    area_desc: str
    effective: Optional[str] = None
    expires: Optional[str] = None
    url: str
    is_fire_related: bool


class AlertsResponse(BaseModel):
    alerts: List[AlertOut]
    source: str = "National Weather Service (api.weather.gov)"
    checked_at: str
    note: str = (
        "These are real, currently active NWS alerts for this location — not alerts EmberReady "
        "generates. An empty list means NWS has no active alert here right now, not that "
        "conditions are safe."
    )


@router.get("/alerts", response_model=AlertsResponse)
def get_alerts(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> AlertsResponse:
    try:
        with httpx.Client(timeout=10.0) as client:
            readings = get_active_alerts(lat, lon, client=client)
    except AlertsFetchError as exc:
        raise HTTPException(status_code=502, detail=f"Alerts data unavailable: {exc}") from exc

    return AlertsResponse(
        alerts=[
            AlertOut(
                event=a.event,
                headline=a.headline,
                severity=a.severity,
                urgency=a.urgency,
                area_desc=a.area_desc,
                effective=a.effective.isoformat() if a.effective else None,
                expires=a.expires.isoformat() if a.expires else None,
                url=a.url,
                is_fire_related=a.is_fire_related,
            )
            for a in readings
        ],
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
