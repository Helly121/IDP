"""
Async SQLAlchemy database engine and session management.
Supports both PostgreSQL (asyncpg) and SQLite (aiosqlite).
Provides a dependency-injectable async session for FastAPI routes.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# SQLite doesn't support pool_size / max_overflow
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs = {
    "echo": settings.DEBUG,
}

if not _is_sqlite:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

if _is_sqlite:
    # SQLite needs check_same_thread=False for async usage
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


async def get_db():
    """
    FastAPI dependency that yields an async database session.
    Automatically commits on success, rolls back on error.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables defined in the ORM models."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose of the database engine connection pool."""
    await engine.dispose()
