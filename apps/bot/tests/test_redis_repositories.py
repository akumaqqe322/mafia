import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.core.game.schemas import GameState, GamePhase
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry


@pytest.fixture
def mock_redis_client() -> MagicMock:
    redis_client = MagicMock()
    redis_client.client = AsyncMock()
    return redis_client


@pytest.fixture
def game_state_repo(mock_redis_client: MagicMock) -> RedisGameStateRepository:
    return RedisGameStateRepository(mock_redis_client)


@pytest.fixture
def active_game_registry(mock_redis_client: MagicMock) -> ActiveGameRegistry:
    return ActiveGameRegistry(mock_redis_client)


@pytest.mark.asyncio
async def test_save_and_get_game_state(
    game_state_repo: RedisGameStateRepository, mock_redis_client: MagicMock
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
    mock_redis_client.client.set.assert_called_once()
    key = f"game:{game_id}:state"
    assert mock_redis_client.client.set.call_args[0][0] == key
    assert isinstance(mock_redis_client.client.set.call_args[0][1], str)

    # Test Get
    mock_redis_client.client.get.return_value = state.to_json().encode("utf-8")
    retrieved_state = await game_state_repo.get(game_id)
    
    assert retrieved_state is not None
    assert retrieved_state.game_id == game_id
    assert retrieved_state.phase == GamePhase.LOBBY


@pytest.mark.asyncio
async def test_get_missing_game_state(
    game_state_repo: RedisGameStateRepository, mock_redis_client: MagicMock
) -> None:
    mock_redis_client.client.get.return_value = None
    retrieved_state = await game_state_repo.get(uuid4())
    assert retrieved_state is None


@pytest.mark.asyncio
async def test_delete_game_state(
    game_state_repo: RedisGameStateRepository, mock_redis_client: MagicMock
) -> None:
    game_id = uuid4()
    await game_state_repo.delete(game_id)
    mock_redis_client.client.delete.assert_called_once_with(f"game:{game_id}:state")


@pytest.mark.asyncio
async def test_exists_game_state(
    game_state_repo: RedisGameStateRepository, mock_redis_client: MagicMock
) -> None:
    game_id = uuid4()
    mock_redis_client.client.exists.return_value = 1
    assert await game_state_repo.exists(game_id) is True
    
    mock_redis_client.client.exists.return_value = 0
    assert await game_state_repo.exists(game_id) is False


@pytest.mark.asyncio
async def test_active_game_registry(
    active_game_registry: ActiveGameRegistry, mock_redis_client: MagicMock
) -> None:
    game_id = uuid4()
    chat_id = 12345

    # Test Add
    await active_game_registry.add_active_game(game_id, chat_id)
    assert mock_redis_client.client.sadd.call_count == 1
    assert mock_redis_client.client.set.call_count == 1
    
    # Test List
    mock_redis_client.client.smembers.return_value = {str(game_id).encode("utf-8")}
    games = await active_game_registry.list_active_games()
    assert len(games) == 1
    assert games[0] == game_id

    # Test Get by Chat
    mock_redis_client.client.get.return_value = str(game_id).encode("utf-8")
    found_game_id = await active_game_registry.get_active_game_by_chat(chat_id)
    assert found_game_id == game_id

    # Test Remove
    await active_game_registry.remove_active_game(game_id, chat_id)
    assert mock_redis_client.client.srem.call_count == 1
    assert mock_redis_client.client.delete.call_count == 1
