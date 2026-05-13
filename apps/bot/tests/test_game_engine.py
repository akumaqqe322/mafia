import pytest
from uuid import UUID, uuid4
from typing import Any
from datetime import datetime, timezone

from app.core.game.engine import (
    GameAlreadyExistsError,
    GameEngine,
    GameFullError,
    GameNotFoundError,
    PlayerAlreadyInGameError,
    PlayerNotInGameError,
)
from app.core.game.locks import GameLockManager
from app.core.game.schemas import GamePhase, GameSettings, GameState
from app.infrastructure.redis import RedisClient
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository

# --- Fakes for Testing ---

class FakeRedisRawClient:
    def __init__(self) -> None:
        self.data: dict[str, str | bytes] = {}
        self.sets: dict[str, set[str | bytes]] = {}

    async def set(self, key: str, value: str | bytes) -> None:
        self.data[key] = value

    async def get(self, key: str) -> str | bytes | None:
        return self.data.get(key)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.sets.pop(key, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self.data or key in self.sets else 0

    async def sadd(self, key: str, value: str | bytes) -> None:
        if key not in self.sets:
            self.sets[key] = set()
        val: str | bytes = value.encode("utf-8") if isinstance(value, str) else value
        self.sets[key].add(val)

    async def srem(self, key: str, value: str | bytes) -> None:
        if key in self.sets:
            val: str | bytes = value.encode("utf-8") if isinstance(value, str) else value
            self.sets[key].discard(val)

    async def smembers(self, key: str) -> set[str | bytes]:
        return self.sets.get(key, set())


class FakeRedisClient(RedisClient):
    def __init__(self) -> None:
        self.client: Any = FakeRedisRawClient()
    async def check_connection(self) -> None: pass
    async def close(self) -> None: pass

# --- Fixtures ---

@pytest.fixture
def fake_redis() -> FakeRedisClient:
    return FakeRedisClient()

@pytest.fixture
def game_engine(fake_redis: FakeRedisClient) -> GameEngine:
    state_repo = RedisGameStateRepository(fake_redis)
    registry = ActiveGameRegistry(fake_redis)
    lock_manager = GameLockManager()
    return GameEngine(state_repo, registry, lock_manager)

# --- Tests ---

@pytest.mark.asyncio
async def test_create_game_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    chat_id = uuid4()
    tg_chat_id = 123
    
    state = await game_engine.create_game(game_id, chat_id, tg_chat_id)
    
    assert state.game_id == game_id
    assert state.phase == GamePhase.LOBBY
    assert len(state.players) == 0
    
    # Verify persistence
    persisted = await game_engine.state_repository.get(game_id)
    assert persisted is not None
    assert persisted.game_id == game_id
    
    # Verify registry
    active_id = await game_engine.active_game_registry.get_active_game_by_chat(tg_chat_id)
    assert active_id == game_id

@pytest.mark.asyncio
async def test_create_game_already_exists(game_engine: GameEngine) -> None:
    tg_chat_id = 123
    await game_engine.create_game(uuid4(), uuid4(), tg_chat_id)
    
    with pytest.raises(GameAlreadyExistsError):
        await game_engine.create_game(uuid4(), uuid4(), tg_chat_id)

@pytest.mark.asyncio
async def test_join_game_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    
    user_id = uuid4()
    state = await game_engine.join_game(game_id, user_id, 456, "Player 1")
    
    assert len(state.players) == 1
    assert state.players[0].user_id == user_id
    assert state.players[0].display_name == "Player 1"
    assert state.version == 2

@pytest.mark.asyncio
async def test_join_game_duplicate(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    user_id = uuid4()
    await game_engine.join_game(game_id, user_id, 456, "Player 1")
    
    with pytest.raises(PlayerAlreadyInGameError):
        await game_engine.join_game(game_id, user_id, 456, "Player 1")

@pytest.mark.asyncio
async def test_join_game_full(game_engine: GameEngine) -> None:
    game_id = uuid4()
    settings = GameSettings(max_players=1)
    await game_engine.create_game(game_id, uuid4(), 123, settings=settings)
    
    await game_engine.join_game(game_id, uuid4(), 456, "P1") 
    
    with pytest.raises(GameFullError):
        await game_engine.join_game(game_id, uuid4(), 789, "P2")

@pytest.mark.asyncio
async def test_leave_game_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    user_id = uuid4()
    await game_engine.join_game(game_id, user_id, 456, "Player 1")
    
    state = await game_engine.leave_game(game_id, user_id)
    assert len(state.players) == 0
    assert state.version == 3

@pytest.mark.asyncio
async def test_leave_game_not_found(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    
    with pytest.raises(PlayerNotInGameError):
        await game_engine.leave_game(game_id, uuid4())

@pytest.mark.asyncio
async def test_cancel_game_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    tg_chat_id = 123
    await game_engine.create_game(game_id, uuid4(), tg_chat_id)
    
    await game_engine.cancel_game(game_id)
    
    assert await game_engine.state_repository.get(game_id) is None
    assert await game_engine.active_game_registry.get_active_game_by_chat(tg_chat_id) is None

@pytest.mark.asyncio
async def test_game_not_found_errors(game_engine: GameEngine) -> None:
    game_id = uuid4()
    user_id = uuid4()
    
    with pytest.raises(GameNotFoundError):
        await game_engine.join_game(game_id, user_id, 1, "Name")
        
    with pytest.raises(GameNotFoundError):
        await game_engine.leave_game(game_id, user_id)
        
    with pytest.raises(GameNotFoundError):
        await game_engine.cancel_game(game_id)
