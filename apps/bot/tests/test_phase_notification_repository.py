from uuid import uuid4
import pytest
from app.infrastructure.repositories.phase_notification_repository import PhaseNotificationRepository
from tests.fakes.redis import FakeRedisClient


@pytest.mark.asyncio
async def test_try_mark_notified_first_call_true() -> None:
    redis = FakeRedisClient()
    repo = PhaseNotificationRepository(redis)
    game_id = uuid4()
    version = 1

    result = await repo.try_mark_notified(game_id, version)
    assert result is True


@pytest.mark.asyncio
async def test_try_mark_notified_second_call_false() -> None:
    redis = FakeRedisClient()
    repo = PhaseNotificationRepository(redis)
    game_id = uuid4()
    version = 1

    await repo.try_mark_notified(game_id, version)
    result = await repo.try_mark_notified(game_id, version)
    assert result is False


@pytest.mark.asyncio
async def test_try_mark_notified_different_version_true() -> None:
    redis = FakeRedisClient()
    repo = PhaseNotificationRepository(redis)
    game_id = uuid4()

    assert await repo.try_mark_notified(game_id, 1) is True
    assert await repo.try_mark_notified(game_id, 2) is True


@pytest.mark.asyncio
async def test_try_mark_notified_different_game_true() -> None:
    redis = FakeRedisClient()
    repo = PhaseNotificationRepository(redis)
    game1 = uuid4()
    game2 = uuid4()
    version = 1

    assert await repo.try_mark_notified(game1, version) is True
    assert await repo.try_mark_notified(game2, version) is True


@pytest.mark.asyncio
async def test_try_mark_notified_uses_expected_key() -> None:
    redis = FakeRedisClient()
    repo = PhaseNotificationRepository(redis)
    game_id = uuid4()
    version = 5

    await repo.try_mark_notified(game_id, version)
    
    # Check underlying fake data
    expected_key = f"game_notify:{game_id}:{version}"
    val = await redis.client.get(expected_key)
    assert val == "1"


@pytest.mark.asyncio
async def test_clear_game_is_safe_noop() -> None:
    redis = FakeRedisClient()
    repo = PhaseNotificationRepository(redis)
    # Should not raise
    await repo.clear_game(uuid4())
