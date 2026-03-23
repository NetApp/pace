"""FastAPI application factory."""

from fastapi import FastAPI

from orchestrio import __version__
from orchestrio.api.routes import router


def create_app() -> FastAPI:
    """Build and return the Orchestrio API application."""
    app = FastAPI(
        title="Orchestrio",
        description="Language-agnostic REST API workflow executor",
        version=__version__,
    )
    app.include_router(router, prefix="/api/v1")
    return app


# Module-level instance for `uvicorn orchestrio.api.app:app`
app = create_app()
