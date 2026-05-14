from uuid import uuid4

import pytest

from app.infrastructure.repositories.player_game_repository import PlayerGameRepository
from tests.fakes.redis import FakeRedisClient


@pytest.mark.asyncio
async def test_player_game_repository_roundtrip() -> None:
    redis = FakeRedisClient()
    repo = PlayerGameRepository(redis)
    telegram_id = 12345
    game_id = uuid4()

    # Initial state
    assert await repo.get_active_game(telegram_id) is None

    # Set
    await repo.set_active_game(telegram_id, game_id)

    # Get
    result = await repo.get_active_game(telegram_id)
    assert result == game_id


@pytest.mark.asyncio
async def test_player_game_repository_clear() -> None:
    redis = FakeRedisClient()
    repo = PlayerGameRepository(redis)
    telegram_id = 12345
    game_id = uuid4()

    await repo.set_active_game(telegram_id, game_id)
    assert await repo.get_active_game(telegram_id) == game_id

    await repo.clear_active_game(telegram_id)
    assert await repo.get_active_game(telegram_id) is None


@pytest.mark.asyncio
async def test_player_game_repository_remove_alias() -> None:
    redis = FakeRedisClient()
    repo = PlayerGameRepository(redis)
    telegram_id = 12345
    game_id = uuid4()

    await repo.set_active_game(telegram_id, game_id)
    await repo.remove_active_game(telegram_id)
    assert await repo.get_active_game(telegram_id) is None


@pytest.mark.asyncio
async def test_player_game_repository_invalid_uuid() -> None:
    redis = FakeRedisClient()
    repo = PlayerGameRepository(redis)
    telegram_id = 12345

    # Insert garbage into redis directly
    key = f"player_game:{telegram_id}"
    await redis.client.set(key, "not-a-uuid")

    assert await repo.get_active_game(telegram_id) is None


@pytest.mark.asyncio
async def test_player_game_repository_bytes_decoding() -> None:
    redis = FakeRedisClient()
    repo = PlayerGameRepository(redis)
    telegram_id = 12345
    game_id = uuid4()

    # Insert bytes into redis directly
    key = f"player_game:{telegram_id}"
    await redis.client.set(key, str(game_id).encode("utf-8"))

    result = await repo.get_active_game(telegram_id)
    assert result == game_id
