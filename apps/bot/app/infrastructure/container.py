from app.core.config import Settings, get_settings
from app.infrastructure.database import Database, db
from app.infrastructure.redis import RedisClient, redis_client


class Container:
    def __init__(self) -> None:
        self.db: Database = db
        self.redis: RedisClient = redis_client
        self.settings: Settings = get_settings()


container = Container()
