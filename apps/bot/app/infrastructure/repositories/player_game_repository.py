from uuid import UUID

from app.infrastructure.redis import RedisClient


class PlayerGameRepository:
    """
    Stores mapping from telegram_id to game_id.
    Used for routing callbacks from private messages to the correct game.
    """

    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis
        self.prefix = "player_game"
        self.ttl = 86400  # 24 hours

    def _get_key(self, telegram_id: int) -> str:
        return f"{self.prefix}:{telegram_id}"

    async def set_active_game(self, telegram_id: int, game_id: UUID) -> None:
        key = self._get_key(telegram_id)
        await self.redis.set(key, str(game_id), ex=self.ttl)

    async def get_active_game(self, telegram_id: int) -> UUID | None:
        key = self._get_key(telegram_id)
        result = await self.redis.get(key)
        if result:
            if isinstance(result, bytes):
                result = result.decode()
            try:
                return UUID(result)
            except (ValueError, TypeError):
                return None
        return None

    async def clear_active_game(self, telegram_id: int) -> None:
        key = self._get_key(telegram_id)
        await self.redis.delete(key)

    async def remove_active_game(self, telegram_id: int) -> None:
        """Alias for clear_active_game for compatibility."""
        await self.clear_active_game(telegram_id)
