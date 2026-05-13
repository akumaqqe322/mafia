from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from app.core.config import get_settings
import structlog

log = structlog.get_logger()

class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            echo=False,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def check_connection(self) -> None:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            log.info("Database connection successful")
        except Exception as e:
            log.error("Database connection failed", error=str(e))
            raise

    async def close(self) -> None:
        await self.engine.dispose()
        log.info("Database connection closed")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

settings = get_settings()
db = Database(settings.DATABASE_URL)
