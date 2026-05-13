from uuid import UUID

from app.core.game.schemas import GameState
from app.infrastructure.redis import RedisClient


class RedisGameStateRepository:
    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis

    def _get_key(self, game_id: UUID) -> str:
        return f"game:{game_id}:state"

    async def save(self, state: GameState) -> None:
        key = self._get_key(state.game_id)
        await self.redis.client.set(key, state.to_json())

    async def get(self, game_id: UUID) -> GameState | None:
        key = self._get_key(game_id)
        data = await self.redis.client.get(key)
        if not data:
            return None
        
        if isinstance(data, bytes):
            data = data.decode("utf-8")
            
        return GameState.from_json(data)

    async def delete(self, game_id: UUID) -> None:
        key = self._get_key(game_id)
        await self.redis.client.delete(key)

    async def exists(self, game_id: UUID) -> bool:
        key = self._get_key(game_id)
        exists_count = await self.redis.client.exists(key)
        return bool(exists_count)
