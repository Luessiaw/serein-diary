"""Versioned API router composition."""

from fastapi import APIRouter

from serein.api import auth, entries, health, protected


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(protected.router)
api_router.include_router(entries.router)
