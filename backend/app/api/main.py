from fastapi import APIRouter

from app.api.routes import analysis, health, results, sessions

api_router = APIRouter()
api_router.include_router(sessions.router, tags=["sessions"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(results.router, tags=["results"])
api_router.include_router(health.router, tags=["health"])
