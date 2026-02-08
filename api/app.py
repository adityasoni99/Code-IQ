"""
FastAPI application for Code-IQ (post-MVP API).

Run with: uvicorn api.app:app --reload
"""

from fastapi import FastAPI

from api.routes.v1 import router as v1_router

app = FastAPI(
    title="Code-IQ API",
    description="Generate structured tutorials from GitHub repos or uploaded code.",
    version="0.2.0",
)

app.include_router(v1_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}
