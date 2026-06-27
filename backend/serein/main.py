"""FastAPI application entry point."""

from fastapi import FastAPI

from serein import __version__
from serein.api import api_router
from serein.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Serein API application."""

    resolved_settings = load_settings() if settings is None else settings
    app = FastAPI(
        title="Serein API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = resolved_settings
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
