from uuid import UUID

from app.infrastructure.redis import RedisClient


class ActiveGameRegistry:
    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis
        self._active_games_set_key = "active_games"

    def _get_chat_mapping_key(self, telegram_chat_id: int) -> str:
        return f"chat:{telegram_chat_id}:active_game"

    async def add_active_game(
        self, game_id: UUID, telegram_chat_id: int
    ) -> None:
        # Add to global active games set
        await self.redis.client.sadd(self._active_games_set_key, str(game_id))
        # Add mapping from chat to game
        await self.redis.client.set(
            self._get_chat_mapping_key(telegram_chat_id), str(game_id)
        )

    async def remove_active_game(self, game_id: UUID, telegram_chat_id: int) -> None:
        # Remove from global active games set
        await self.redis.client.srem(self._active_games_set_key, str(game_id))
        # Remove mapping from chat to game
        await self.redis.client.delete(self._get_chat_mapping_key(telegram_chat_id))

    async def list_active_games(self) -> list[UUID]:
        members = await self.redis.client.smembers(self._active_games_set_key)
        # Redis returns bytes or strings depending on configuration
        return [UUID(m.decode("utf-8") if isinstance(m, bytes) else m) for m in members]

    async def get_active_game_by_chat(self, telegram_chat_id: int) -> UUID | None:
        data = await self.redis.client.get(self._get_chat_mapping_key(telegram_chat_id))
        if not data:
            return None
        
        game_id_str = data.decode("utf-8") if isinstance(data, bytes) else data
        return UUID(game_id_str)
