"""FastAPI application factory for the OmniVox gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.admin import router as admin_router
from backend.config.settings import get_settings


def create_app() -> FastAPI:
    """Create the local-first HTTP gateway and its browser-safe CORS policy."""
    settings = get_settings()
    origins = [origin.strip() for origin in settings.admin_cors_origins.split(",") if origin.strip()]
    application = FastAPI(
        title="OmniVox Admin API",
        version="0.5.0",
        description="Tenant-safe operational controls for the OmniVox enterprise voice platform.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )
    application.include_router(admin_router)

    @application.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        """Return a lightweight local readiness probe."""
        return {"status": "ok", "service": "omnivox-admin-api"}

    return application


app = create_app()

