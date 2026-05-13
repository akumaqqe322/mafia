from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.game.schemas import GamePhase, GameState
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import (
    RedisGameStateRepository,
)
from tests.fakes.redis import FakeRedisClient


@pytest.fixture
def fake_redis() -> FakeRedisClient:
    return FakeRedisClient()


@pytest.fixture
def game_state_repo(fake_redis: FakeRedisClient) -> RedisGameStateRepository:
    return RedisGameStateRepository(fake_redis)


@pytest.fixture
def active_game_registry(fake_redis: FakeRedisClient) -> ActiveGameRegistry:
    return ActiveGameRegistry(fake_redis)


@pytest.mark.asyncio
async def test_save_and_get_game_state(
    game_state_repo: RedisGameStateRepository,
) -> None:
    game_id = uuid4()
    state = GameState(
        game_id=game_id,
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
    )

    # Test Save
    await game_state_repo.save(state)

    # Test Get
    retrieved_state = await game_state_repo.get(game_id)

    assert retrieved_state is not None
    assert retrieved_state.game_id == game_id
    assert retrieved_state.phase == GamePhase.LOBBY
    assert retrieved_state.telegram_chat_id == 123


@pytest.mark.asyncio
async def test_get_missing_game_state(
    game_state_repo: RedisGameStateRepository,
) -> None:
    retrieved_state = await game_state_repo.get(uuid4())
    assert retrieved_state is None


@pytest.mark.asyncio
async def test_delete_game_state(
    game_state_repo: RedisGameStateRepository,
) -> None:
    game_id = uuid4()
    state = GameState(
        game_id=game_id,
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    await game_state_repo.save(state)
    assert await game_state_repo.exists(game_id) is True

    await game_state_repo.delete(game_id)
    assert await game_state_repo.exists(game_id) is False
    assert await game_state_repo.get(game_id) is None


@pytest.mark.asyncio
async def test_active_game_registry_lifecycle(
    active_game_registry: ActiveGameRegistry,
) -> None:
    game_id = uuid4()
    telegram_chat_id = 12345

    # Initially empty
    assert await active_game_registry.list_active_games() == []
    assert await active_game_registry.get_active_game_by_chat(telegram_chat_id) is None

    # Test Add
    await active_game_registry.add_active_game(game_id, telegram_chat_id)

    # Test List
    games = await active_game_registry.list_active_games()
    assert len(games) == 1
    assert games[0] == game_id

    # Test Get by Chat
    assert (
        await active_game_registry.get_active_game_by_chat(telegram_chat_id) == game_id
    )

    # Test Remove
    await active_game_registry.remove_active_game(game_id, telegram_chat_id)
    assert await active_game_registry.list_active_games() == []
    assert await active_game_registry.get_active_game_by_chat(telegram_chat_id) is None
