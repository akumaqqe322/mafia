from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
import structlog

log = structlog.get_logger()

class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(
            url,
            pool_pre_ping=True,
            echo=False,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def check_connection(self):
        try:
            async with self.engine.connect() as conn:
                await conn.execute("SELECT 1")
            log.info("Database connection successful")
        except Exception as e:
            log.error("Database connection failed", error=str(e))
            raise

    async def close(self):
        await self.engine.dispose()
        log.info("Database connection closed")

db = Database(settings.DATABASE_URL)
