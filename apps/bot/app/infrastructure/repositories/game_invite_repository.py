import secrets
from uuid import UUID

from app.infrastructure.redis import RedisClient


class GameInviteRepository:
    """Manages game invite tokens in Redis."""

    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis
        self._invite_prefix = "game_invite"
        self._game_to_token_prefix = "game_invite_token"

    def _get_invite_key(self, token: str) -> str:
        return f"{self._invite_prefix}:{token}"

    def _get_game_to_token_key(self, game_id: UUID) -> str:
        return f"{self._game_to_token_prefix}:{game_id}"

    async def create_invite(self, game_id: UUID) -> str:
        """Creates a short invite token for a game. Reuses existing token if available."""
        # Reuse existing token if it exists
        game_token_key = self._get_game_to_token_key(game_id)
        existing_token = await self.redis.client.get(game_token_key)
        if existing_token:
            return (
                existing_token.decode("utf-8")
                if isinstance(existing_token, bytes)
                else existing_token
            )

        # Generate new token
        token = secrets.token_urlsafe(8)
        invite_key = self._get_invite_key(token)

        # Store mappings in both directions
        await self.redis.client.set(invite_key, str(game_id))
        await self.redis.client.set(game_token_key, token)

        return token

    async def get_game_id(self, token: str) -> UUID | None:
        """Resolves game_id by token."""
        invite_key = self._get_invite_key(token)
        data = await self.redis.client.get(invite_key)
        if not data:
            return None

        game_id_str = data.decode("utf-8") if isinstance(data, bytes) else data
        return UUID(game_id_str)

    async def delete_invite(self, token: str) -> None:
        """Deletes an invite by token."""
        game_id = await self.get_game_id(token)
        if game_id:
            await self.redis.client.delete(self._get_invite_key(token))
            await self.redis.client.delete(self._get_game_to_token_key(game_id))

    async def delete_by_game_id(self, game_id: UUID) -> None:
        """Deletes invite associated with game_id."""
        game_token_key = self._get_game_to_token_key(game_id)
        token_data = await self.redis.client.get(game_token_key)
        if token_data:
            token = (
                token_data.decode("utf-8")
                if isinstance(token_data, bytes)
                else token_data
            )
            await self.redis.client.delete(self._get_invite_key(token))
            await self.redis.client.delete(game_token_key)
