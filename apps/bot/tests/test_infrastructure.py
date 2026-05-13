import pytest
from app.infrastructure.database import Database
from app.infrastructure.redis import RedisClient
from app.core.config import get_settings

def test_database_init():
    settings = get_settings()
    db = Database(settings.DATABASE_URL)
    assert db.engine is not None

def test_redis_init():
    settings = get_settings()
    redis_client = RedisClient(settings.REDIS_URL)
    assert redis_client.client is not None
