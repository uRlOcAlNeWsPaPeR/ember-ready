import sys
from pathlib import Path

# Vercel's Python runtime imports this file directly by absolute path and
# does not run it with `backend/` as the working directory the way
# `cd backend && uvicorn app.main:app` does locally — so `app` isn't
# importable as a top-level package unless `backend/` is on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# Loads backend/.env into the process environment (e.g. GEMINI_API_KEY) for
# local dev, before any app module reads os.environ at import time. A
# no-op if the file doesn't exist — Vercel/Render/Railway set real
# environment variables directly, never through this file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    ai_explain as ai_explain_api,
    air_quality as air_quality_api,
    alerts as alerts_api,
    checklist,
    geocode as geocode_api,
    map as map_api,
    score,
    seismic as seismic_api,
)

app = FastAPI(
    title="EmberReady API",
    description=(
        "Educational, U.S.-only wildfire preparedness API. Not an emergency alert system "
        "or an official fire-risk determination — see /api/score's disclaimer field."
    ),
    version="0.1.0",
)

# Permissive for hackathon demo purposes; tighten allow_origins for a real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(score.router, prefix="/api", tags=["score"])
app.include_router(checklist.router, prefix="/api", tags=["checklist"])
app.include_router(map_api.router, prefix="/api", tags=["map"])
app.include_router(geocode_api.router, prefix="/api", tags=["geocode"])
app.include_router(air_quality_api.router, prefix="/api", tags=["air-quality"])
app.include_router(alerts_api.router, prefix="/api", tags=["alerts"])
app.include_router(seismic_api.router, prefix="/api", tags=["seismic"])
app.include_router(ai_explain_api.router, prefix="/api", tags=["ai"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serve the plain HTML/CSS/JS frontend from the same process, so the whole
# app is one command locally and one service on Render/Railway. Mounted
# last so it never shadows the /api/* and /health routes above.
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
