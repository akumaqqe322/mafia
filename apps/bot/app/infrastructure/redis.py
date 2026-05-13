import redis.asyncio as redis
from app.core.config import get_settings
import structlog

log = structlog.get_logger()

class RedisClient:
    def __init__(self, url: str) -> None:
        self.client: redis.Redis = redis.from_url(url, decode_responses=True)

    async def check_connection(self) -> None:
        try:
            await self.client.ping()
            log.info("Redis connection successful")
        except Exception as e:
            log.error("Redis connection failed", error=str(e))
            raise

    async def close(self) -> None:
        await self.client.aclose()
        log.info("Redis connection closed")

settings = get_settings()
redis_client = RedisClient(settings.REDIS_URL)
