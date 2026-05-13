from app.infrastructure.database import db
from app.infrastructure.redis import redis_client

class Container:
    def __init__(self):
        self.db = db
        self.redis = redis_client

container = Container()
