import pytest

from app.core.config import get_settings
from app.infrastructure.database import Database
from app.infrastructure.redis import RedisClient


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()


def test_database_init() -> None:
    settings = get_settings()
    db = Database(settings.DATABASE_URL)
    assert db.engine is not None


def test_redis_init() -> None:
    settings = get_settings()
    redis_client = RedisClient(settings.REDIS_URL)
    assert redis_client.client is not None
