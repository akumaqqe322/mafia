import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()


def test_settings_load() -> None:
    # It should load without error with mocked env
    settings = get_settings()
    assert settings.ENVIRONMENT == "test"
    assert settings.BOT_TOKEN.get_secret_value() == "test_token"


def test_settings_lru_cache() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
