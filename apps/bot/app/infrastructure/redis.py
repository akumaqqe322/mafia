import redis.asyncio as redis
from app.core.config import settings
import structlog

log = structlog.get_logger()

class RedisClient:
    def __init__(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)

    async def check_connection(self):
        try:
            await self.client.ping()
            log.info("Redis connection successful")
        except Exception as e:
            log.error("Redis connection failed", error=str(e))
            raise

    async def close(self):
        await self.client.aclose()
        log.info("Redis connection closed")

redis_client = RedisClient(settings.REDIS_URL)
