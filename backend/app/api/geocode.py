"""Typeahead suggestions for the address/ZIP search box — separate from
/api/score's actual resolver chain (Census first, Open-Meteo fallback).
Suggestions are sourced from Open-Meteo only, since Census's geocoder has
no partial-query/autocomplete endpoint (it only matches complete, well-
formed addresses) — verified against their live API before building this.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.geocode.openmeteo_geo import search_suggestions

router = APIRouter()

MIN_QUERY_LENGTH = 2
MAX_SUGGESTIONS = 5


class SuggestionOut(BaseModel):
    label: str
    latitude: float
    longitude: float


class SuggestResponse(BaseModel):
    suggestions: list[SuggestionOut]


@router.get("/geocode/suggest", response_model=SuggestResponse)
def get_suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="Partial city, town, or ZIP code"),
) -> SuggestResponse:
    if len(q.strip()) < MIN_QUERY_LENGTH:
        return SuggestResponse(suggestions=[])

    try:
        with httpx.Client(timeout=5.0) as client:
            results = search_suggestions(q.strip(), count=MAX_SUGGESTIONS, client=client)
    except httpx.HTTPError:
        # Suggestions are a nice-to-have; never break the search box over it.
        return SuggestResponse(suggestions=[])

    return SuggestResponse(suggestions=[SuggestionOut(**r) for r in results])
