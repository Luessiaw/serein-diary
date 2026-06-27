"""Health check routes.

P3-T02 only reserves the route module. The actual /health endpoint is
implemented in P3-T04.
"""

from fastapi import APIRouter


router = APIRouter(tags=["health"])

