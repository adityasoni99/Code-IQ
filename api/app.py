"""
FastAPI application for Code-IQ (post-MVP API).

Run with:
  uvicorn api.app:app --reload --reload-exclude '.cache' --reload-exclude 'output'
Excluding .cache and output prevents reloads when cloning repos or writing tutorials.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from api.routes.v1 import router as v1_router

# CORS origins for React dev server (configurable via CORS_ORIGINS env, comma-separated)
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app = FastAPI(
    title="Code-IQ API",
    description="Generate structured tutorials from GitHub repos or uploaded code.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}
