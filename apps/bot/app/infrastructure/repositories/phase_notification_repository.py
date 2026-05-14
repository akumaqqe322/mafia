from uuid import UUID
from app.infrastructure.redis import RedisClient


class PhaseNotificationRepository:
    """
    Stores which game state versions have been notified.
    Used to prevent duplicate Telegram notifications.
    """

    def __init__(self, redis: RedisClient, ttl_seconds: int = 86400) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.prefix = "game_notify"

    def _get_key(self, game_id: UUID, version: int) -> str:
        return f"{self.prefix}:{game_id}:{version}"

    async def try_mark_notified(self, game_id: UUID, version: int) -> bool:
        """
        Atomically marks a game state version as notified.
        Returns True if this version was not marked before.
        Returns False if it was already marked.
        """
        key = self._get_key(game_id, version)
        # Using SET key "1" NX EX ttl
        # redis-py set returns True or 'OK' on success with nx=True, None otherwise
        result = await self.redis.client.set(key, "1", nx=True, ex=self.ttl_seconds)

        return result is True or result == "OK" or result == b"OK"

    async def clear_game(self, game_id: UUID) -> None:
        """
        Best-effort cleanup for notification keys of a game.
        For MVP, we rely on TTL to clean up these keys automatically.
        """
        pass
