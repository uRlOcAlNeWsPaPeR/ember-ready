from __future__ import annotations

import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Optional AI feature: turns the *same* numbers already shown in the score
# panel into a plain-language paragraph. Deliberately not a general chatbot —
# the prompt only ever hands the model facts already computed by our own
# scoring pipeline and tells it not to add anything new, so this can't
# introduce a fabricated risk claim the way an open-ended assistant could.
# Degrades quietly (503/502) when no key is configured or the call fails —
# the deterministic explainer sentence in score-panel.js is always shown
# regardless, so this is a pure enhancement, never a dependency.
router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


class ExplainFactor(BaseModel):
    name: str
    available: bool
    raw_value: Optional[float] = None
    raw_unit: Optional[str] = None
    contribution_points: Optional[float] = None


class ExplainRequest(BaseModel):
    location: str
    status_label: str
    baseline_label: str
    weather_label: str
    factors: List[ExplainFactor]
    safety_notice: str


class ExplainResponse(BaseModel):
    explanation: str
    model: str


def _build_prompt(payload: ExplainRequest) -> str:
    factor_lines = []
    for f in payload.factors:
        clean_name = f.name.replace("_", " ")
        if f.available:
            factor_lines.append(
                f"- {clean_name}: {f.raw_value} {f.raw_unit or ''} (contributed {f.contribution_points} pts)"
            )
        else:
            factor_lines.append(f"- {clean_name}: not available, excluded from the score")
    factor_block = "\n".join(factor_lines)

    return (
        "You are explaining a wildfire risk score to a member of the public in plain, calm "
        "language. You must ONLY use the facts given below — never invent a statistic, cause, "
        "or recommendation that isn't already present in this data. Do not give evacuation, "
        "firefighting, or other safety instructions beyond what is already stated. Write 2-4 "
        "short sentences of plain English prose, no bullet points, no markdown, no headers.\n\n"
        f"Location: {payload.location}\n"
        f"Overall status: {payload.status_label}\n"
        f"Long-term area hazard: {payload.baseline_label}\n"
        f"Today's fire weather: {payload.weather_label}\n"
        f"Factors:\n{factor_block}\n\n"
        f"Official safety notice already shown to the user: {payload.safety_notice}\n\n"
        "Explain what is driving this score."
    )


@router.post("/explain", response_model=ExplainResponse)
def explain_score(payload: ExplainRequest) -> ExplainResponse:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="AI explanation is not configured on this server.")

    try:
        resp = httpx.post(
            GEMINI_URL,
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": _build_prompt(payload)}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 220},
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail="Could not generate an AI explanation right now.") from exc

    return ExplainResponse(explanation=text, model=GEMINI_MODEL)
