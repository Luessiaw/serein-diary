"""Health check routes."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from serein import __version__
from serein.config import Settings


router = APIRouter(tags=["health"])


class HealthConfigStatus(BaseModel):
    """Safe configuration status for health responses."""

    ready: bool
    data_dir: str
    timezone: str


class HealthResponse(BaseModel):
    """Public health response."""

    status: str
    version: str
    config: HealthConfigStatus


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    """Return safe application health details.

    The response intentionally does not expose the real data directory path,
    secrets, passwords, cookies, or diary content.
    """

    settings: Settings = request.app.state.settings
    return build_health_response(settings)


def build_health_response(settings: Settings) -> HealthResponse:
    """Build a safe health response from validated settings."""

    return HealthResponse(
        status="ok",
        version=__version__,
        config=HealthConfigStatus(
            ready=True,
            data_dir="configured",
            timezone=settings.timezone,
        ),
    )
