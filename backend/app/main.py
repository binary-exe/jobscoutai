"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.core.database import db
from backend.app.api import jobs, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    # Connect to database
    if not settings.use_sqlite:
        await db.connect()
        print(f"[DB] Connected to Postgres")
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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(jobs.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)

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
