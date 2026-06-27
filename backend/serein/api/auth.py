"""Lock-screen access protection routes.

P3-T02 only reserves the route module. The actual login, logout, and session
handlers are implemented in P3-T05.
"""

from fastapi import APIRouter


router = APIRouter(prefix="/auth", tags=["auth"])

