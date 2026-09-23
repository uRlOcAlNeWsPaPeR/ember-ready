from __future__ import annotations

import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Optional AI features: turn numbers/state we've already computed into a
# plain-language paragraph. Deliberately not a general chatbot — every
# prompt here only ever hands the model facts already known to our own
# pipeline or already tracked in the user's own local checklist state, and
# tells it not to add anything new, so this can't introduce a fabricated
# risk claim or a fabricated preparedness step the way an open-ended
# assistant could. Degrades quietly (503/502) when no key is configured or
# the call fails — every deterministic UI element these buttons sit next to
# is always shown regardless, so these are pure enhancements, never a
# dependency.
router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# EmberReady runs these AI features on Gemini's free tier, which has a real
# daily/per-minute quota — shown to the user instead of a generic error so
# a rate limit doesn't read as "broken." A single message here, reused by
# both frontend AI buttons via the response body, so the wording only lives
# in one place.
QUOTA_MESSAGE = (
    "AI features are on a free usage plan and that plan's limit has been "
    "reached for the moment — EmberReady is a small independent project, "
    "not a funded service. This will resolve once the limit resets; "
    "everything else in the app is unaffected."
)


def _call_gemini(prompt: str, max_output_tokens: int = 220) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="AI generation is not configured on this server.")

    try:
        resp = httpx.post(
            GEMINI_URL,
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": max_output_tokens,
                    # These are short, single-turn rewrites of data we already
                    # trust, not reasoning tasks — thinking mode only adds
                    # multi-second latency here (measured ~15s+ vs ~2s off).
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the AI service right now.") from exc

    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail=QUOTA_MESSAGE)

    try:
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail="Could not generate an AI response right now.") from exc


# --- Risk score explanation ------------------------------------------------


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


def _build_explain_prompt(payload: ExplainRequest) -> str:
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
    text = _call_gemini(_build_explain_prompt(payload))
    return ExplainResponse(explanation=text, model=GEMINI_MODEL)


# --- Preparedness plan summary ---------------------------------------------


class PlanItem(BaseModel):
    category: str
    text: str
    done: bool


class PlanSummaryRequest(BaseModel):
    hazard: str  # "wildfire" or "earthquake"
    items: List[PlanItem]


class PlanSummaryResponse(BaseModel):
    summary: str
    model: str


def _build_plan_prompt(payload: PlanSummaryRequest) -> str:
    done_items = [i.text for i in payload.items if i.done]
    todo_items = [i.text for i in payload.items if not i.done]
    done_block = "\n".join(f"- {t}" for t in done_items) or "(none yet)"
    todo_block = "\n".join(f"- {t}" for t in todo_items) or "(none — everything below is already done)"
    hazard_word = "wildfire" if payload.hazard == "wildfire" else "earthquake"

    return (
        f"You are encouraging someone with their {hazard_word} preparedness checklist, based "
        "only on their own real progress below. You must ONLY reference the items listed — "
        "never invent a new preparedness step, statistic, or safety instruction that isn't "
        "already in this list. Write 2-4 short sentences of plain, warm, encouraging English "
        "prose, no bullet points, no markdown, no headers. Briefly acknowledge what's already "
        "done, then name one or two concrete remaining items to prioritize next, describing "
        "them close to how they're written below.\n\n"
        f"Already done:\n{done_block}\n\n"
        f"Not done yet:\n{todo_block}\n"
    )


@router.post("/plan-summary", response_model=PlanSummaryResponse)
def summarize_plan(payload: PlanSummaryRequest) -> PlanSummaryResponse:
    text = _call_gemini(_build_plan_prompt(payload), max_output_tokens=200)
    return PlanSummaryResponse(summary=text, model=GEMINI_MODEL)
