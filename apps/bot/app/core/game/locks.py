import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID


class GameLockManager:
    """Manages in-process locks for game state mutations."""
    
    def __init__(self) -> None:
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    async def get_lock(self, game_id: UUID) -> asyncio.Lock:
        """Get or create lock for a specific game id."""
        async with self._registry_lock:
            if game_id not in self._locks:
                self._locks[game_id] = asyncio.Lock()
            return self._locks[game_id]

    @asynccontextmanager
    async def lock(self, game_id: UUID) -> AsyncIterator[None]:
        """Lock context manager for a specific game."""
        lock = await self.get_lock(game_id)
        async with lock:
            yield
