"""FastAPI application entry point."""

from fastapi import FastAPI

from serein import __version__
from serein.api import api_router


def create_app() -> FastAPI:
    """Create and configure the Serein API application."""

    app = FastAPI(
        title="Serein API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

