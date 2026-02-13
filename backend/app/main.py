"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
import re

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.config import get_settings
from backend.app.core.database import db
from backend.app.api import jobs, admin, apply, paddle, scrape, runs, profile, referrals, saved_searches, metrics, premium_ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    # Connect to database
    if not settings.use_sqlite:
        await db.connect()
        print(f"[DB] Connected to Postgres")
        # Ensure schema exists (idempotent)
        try:
            from backend.app.storage.postgres import init_schema
            async with db.connection() as conn:
                await init_schema(conn)
        except Exception as e:
            # Don't crash the app on schema init errors; surface them in logs.
            print(f"[DB] Schema init failed: {e}")
    else:
        print(f"[DB] Using SQLite: {settings.sqlite_path}")

    # Start scheduler if not in debug mode
    if not settings.debug:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from backend.app.worker import run_scheduled_scrape

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            run_scheduled_scrape,
            "interval",
            hours=settings.scrape_interval_hours,
            id="scheduled_scrape",
        )
        scheduler.start()
        print(f"[Scheduler] Started, running every {settings.scrape_interval_hours}h")

    yield

    # Cleanup
    if not settings.use_sqlite:
        await db.disconnect()


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    settings = get_settings()

    # Allow browser extensions (Chrome/Edge) to call the API directly.
    # We keep the standard web origins allowlist, and add a regex for extension origins.
    _extension_origin_re = re.compile(r"^chrome-extension://[a-z0-9_-]+$", re.IGNORECASE)

    def _is_allowed_origin(origin: str | None) -> bool:
        if not origin:
            return False
        if origin in settings.cors_origins:
            return True
        return bool(_extension_origin_re.match(origin))

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="High-accuracy job aggregator API",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=_extension_origin_re.pattern,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers to ensure CORS headers are always sent
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Ensure CORS headers are sent even on HTTP exceptions."""
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
        # Add CORS headers manually
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Ensure CORS headers are sent even on validation errors."""
        response = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )
        # Add CORS headers manually
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Ensure CORS headers are sent even on unhandled exceptions."""
        import traceback
        print(f"Unhandled exception: {exc}")
        print(traceback.format_exc())
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
        # Add CORS headers manually
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    # Routes
    app.include_router(jobs.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)
    app.include_router(apply.router, prefix=settings.api_prefix)
    app.include_router(profile.router, prefix=settings.api_prefix)
    app.include_router(paddle.router, prefix=settings.api_prefix)
    app.include_router(scrape.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)
    app.include_router(referrals.router, prefix=settings.api_prefix)
    app.include_router(saved_searches.router, prefix=settings.api_prefix)
    app.include_router(metrics.router, prefix=settings.api_prefix)
    app.include_router(premium_ai.router, prefix=settings.api_prefix)

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
