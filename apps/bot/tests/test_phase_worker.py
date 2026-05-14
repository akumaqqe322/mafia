import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.game.engine import GameEngine
from app.core.game.locks import GameLockManager
from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import (
    RedisGameStateRepository,
)
from app.workers.phase_worker import PhaseWorker
from tests.fakes.redis import FakeRedisClient


@pytest.fixture
def fake_redis() -> FakeRedisClient:
    return FakeRedisClient()


@pytest.fixture
def repositories(
    fake_redis: FakeRedisClient,
) -> tuple[RedisGameStateRepository, ActiveGameRegistry]:
    state_repo = RedisGameStateRepository(fake_redis)
    registry = ActiveGameRegistry(fake_redis)
    return state_repo, registry


@pytest.fixture
def game_engine(
    repositories: tuple[RedisGameStateRepository, ActiveGameRegistry],
) -> GameEngine:
    state_repo, registry = repositories
    lock_manager = GameLockManager()
    return GameEngine(state_repo, registry, lock_manager)


@pytest.fixture
def phase_worker(
    game_engine: GameEngine,
    repositories: tuple[RedisGameStateRepository, ActiveGameRegistry],
) -> PhaseWorker:
    state_repo, registry = repositories
    return PhaseWorker(game_engine, state_repo, registry)


@pytest.mark.asyncio
async def test_tick_advances_expired_game(
    phase_worker: PhaseWorker, game_engine: GameEngine
) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)

    # Setup game in NIGHT phase but expired
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")

    # Manually set phase_end_at to the past
    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    now = datetime.now(timezone.utc)
    state.phase_end_at = now - timedelta(seconds=10)
    await game_engine.state_repository.save(state)

    # Run tick
    count = await phase_worker.tick(now=now)

    assert count == 1
    new_state = await game_engine.state_repository.get(game_id)
    assert new_state is not None
    assert new_state.phase == GamePhase.DAY


@pytest.mark.asyncio
async def test_tick_advances_day_to_voting(
    phase_worker: PhaseWorker, game_engine: GameEngine
) -> None:
    game_id = uuid4()
    tg_chat_id = 123
    await game_engine.create_game(game_id, uuid4(), tg_chat_id)

    # 1 mafia + 3 civilians
    p_mafia = uuid4()
    p_civs = [uuid4() for _ in range(3)]
    for i, p_id in enumerate([p_mafia] + p_civs):
        await game_engine.join_game(game_id, p_id, 1000 + i, f"P {i}")

    # Setup game in DAY phase expired
    async with game_engine.lock_manager.lock(game_id):
        state = await game_engine.state_repository.get(game_id)
        assert state is not None
        state.phase = GamePhase.DAY
        # Assign roles to prevent victory draw
        state.players[0].role = RoleId.MAFIA.value
        for i in range(1, 4):
            state.players[i].role = RoleId.CIVILIAN.value

        now = datetime.now(timezone.utc)
        state.phase_end_at = now - timedelta(seconds=10)
        await game_engine.state_repository.save(state)

    count = await phase_worker.tick(now=now)
    assert count == 1
    new_state = await game_engine.state_repository.get(game_id)
    assert new_state is not None
    assert new_state.phase == GamePhase.VOTING
    assert new_state.winner_side is None


@pytest.mark.asyncio
async def test_tick_advances_voting_to_night(
    phase_worker: PhaseWorker, game_engine: GameEngine
) -> None:
    game_id = uuid4()
    tg_chat_id = 123
    await game_engine.create_game(game_id, uuid4(), tg_chat_id)

    # 1 mafia + 3 civilians
    p_mafia = uuid4()
    p_civs = [uuid4() for _ in range(3)]
    for i, p_id in enumerate([p_mafia] + p_civs):
        await game_engine.join_game(game_id, p_id, 1000 + i, f"P {i}")

    # Setup game in VOTING phase expired
    async with game_engine.lock_manager.lock(game_id):
        state = await game_engine.state_repository.get(game_id)
        assert state is not None
        state.phase = GamePhase.VOTING
        # Assign roles to prevent victory draw
        state.players[0].role = RoleId.MAFIA.value
        for i in range(1, 4):
            state.players[i].role = RoleId.CIVILIAN.value

        state.votes = {}  # Nobody voted -> nobody executed -> no victory
        now = datetime.now(timezone.utc)
        state.phase_end_at = now - timedelta(seconds=10)
        await game_engine.state_repository.save(state)

    count = await phase_worker.tick(now=now)
    assert count == 1
    new_state = await game_engine.state_repository.get(game_id)
    assert new_state is not None
    assert new_state.phase == GamePhase.NIGHT
    assert new_state.winner_side is None


@pytest.mark.asyncio
async def test_tick_does_not_advance_future_game(
    phase_worker: PhaseWorker, game_engine: GameEngine
) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")

    # phase_end_at is in the future by default
    now = datetime.now(timezone.utc)

    count = await phase_worker.tick(now=now)

    assert count == 0
    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.phase == GamePhase.NIGHT


@pytest.mark.asyncio
async def test_tick_skips_game_without_expiry(
    phase_worker: PhaseWorker, game_engine: GameEngine
) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    # LOBBY phase has no phase_end_at by default

    now = datetime.now(timezone.utc)
    count = await phase_worker.tick(now=now)

    assert count == 0
    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.phase == GamePhase.LOBBY


@pytest.mark.asyncio
async def test_tick_skips_missing_state(
    phase_worker: PhaseWorker, game_engine: GameEngine
) -> None:
    game_id = uuid4()
    # Add to registry but don't create state
    await phase_worker.active_game_registry.add_active_game(game_id, 123)

    count = await phase_worker.tick()
    assert count == 0


@pytest.mark.asyncio
async def test_phase_worker_start_stop(phase_worker: PhaseWorker) -> None:
    phase_worker.poll_interval_sec = 0.01
    task = asyncio.create_task(phase_worker.start())

    await asyncio.sleep(0.02)
    phase_worker.stop()

    await asyncio.wait_for(task, timeout=1.0)
    assert not phase_worker.is_running
