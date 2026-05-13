from app.infrastructure.database import db
from app.infrastructure.redis import redis_client
from app.core.config import get_settings

class Container:
    def __init__(self) -> None:
        self.db = db
        self.redis = redis_client
        self.settings = get_settings()

container = Container()
