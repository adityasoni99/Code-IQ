"""API v1 routes."""

from fastapi import APIRouter

from api.routes.v1 import build, jobs, projects

router = APIRouter(prefix="/v1", tags=["v1"])
router.include_router(build.router, tags=["build"])
router.include_router(jobs.router, tags=["jobs"])
router.include_router(projects.router, tags=["projects"])
