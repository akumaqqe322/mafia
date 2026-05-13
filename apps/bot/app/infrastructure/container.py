from app.core.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.redis import RedisClient


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.db: Database = Database(settings.DATABASE_URL)
        self.redis: RedisClient = RedisClient(settings.REDIS_URL)
