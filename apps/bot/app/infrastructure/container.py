from app.core.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.redis import RedisClient
from app.infrastructure.repositories import (
    ChatRepository,
    ChatSettingsRepository,
    UserRepository,
)


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.db: Database = Database(settings.DATABASE_URL)
        self.redis: RedisClient = RedisClient(settings.REDIS_URL)

        # Repositories (will need an AsyncSession passed to them)
        self.user_repository = UserRepository
        self.chat_repository = ChatRepository
        self.chat_settings_repository = ChatSettingsRepository
