"""
Database connection and session management.

Supports both Postgres (production) and SQLite (local dev).
"""

from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

from backend.app.core.config import get_settings


class Database:
    """Async database connection pool."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create connection pool."""
        settings = get_settings()
        if settings.use_sqlite:
            # SQLite handled separately
            return

        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()

    @asynccontextmanager
    async def connection(self):
        """Get a connection from the pool."""
        async with self.pool.acquire() as conn:
            yield conn


# Global database instance
db = Database()
