import pytest
from unittest.mock import AsyncMock

from app.core.config import get_settings
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.infrastructure.repositories.chat_settings_repository import (
    ChatSettingsRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()


def test_repositories_init() -> None:
    # This is a unit test checking if repositories can be instantiated with a session
    session = AsyncMock()

    user_repo = UserRepository(session)
    assert user_repo.session == session

    chat_repo = ChatRepository(session)
    assert chat_repo.session == session

    settings_repo = ChatSettingsRepository(session)
    assert settings_repo.session == session
