from app.core.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.redis import RedisClient
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository
from app.core.game.engine import GameEngine
from app.core.game.locks import GameLockManager


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.db: Database = Database(settings.DATABASE_URL)
        self.redis: RedisClient = RedisClient(settings.REDIS_URL)

        self.game_lock_manager = GameLockManager(self.redis)
        self.game_repository = RedisGameStateRepository(self.redis)
        self.active_game_registry = ActiveGameRegistry(self.redis)
        self.game_engine = GameEngine(
            self.game_repository,
            self.active_game_registry,
            self.game_lock_manager,
        )

    def get_user_repository(self, session) -> UserRepository:
        return UserRepository(session)

    def get_chat_repository(self, session) -> ChatRepository:
        return ChatRepository(session)
