import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.game.engine import GameEngine
from app.core.game.locks import GameLockManager
from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase, GameState, PlayerState
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import (
    RedisGameStateRepository,
)
from app.workers.phase_worker import PhaseWorker, _should_notify_phase_change
from tests.fakes.redis import FakeRedisClient


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[GameState | None, GameState]] = []

    async def notify_phase_change(
        self, old_state: GameState | None, new_state: GameState
    ) -> None:
        self.calls.append((old_state, new_state))


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


@pytest.mark.asyncio
async def test_phase_worker_notifies_on_phase_change(
    game_engine: GameEngine,
    repositories: tuple[RedisGameStateRepository, ActiveGameRegistry],
) -> None:
    state_repo, registry = repositories
    notifier = FakeNotifier()
    worker = PhaseWorker(game_engine, state_repo, registry, notifier=notifier)

    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")
    await game_engine.start_game(game_id, "classic_5_6")

    # Expire game in NIGHT phase
    state = await state_repo.get(game_id)
    assert state is not None
    now = datetime.now(timezone.utc)
    state.phase_end_at = now - timedelta(seconds=1)
    await state_repo.save(state)

    await worker.tick(now=now)

    assert len(notifier.calls) == 1
    old_st, new_st = notifier.calls[0]
    assert old_st is not None
    assert old_st.phase == GamePhase.NIGHT
    assert new_st.phase == GamePhase.DAY


@pytest.mark.asyncio
async def test_phase_worker_does_not_notify_when_no_phase_change(
    game_engine: GameEngine,
    repositories: tuple[RedisGameStateRepository, ActiveGameRegistry],
) -> None:
    state_repo, registry = repositories
    notifier = FakeNotifier()
    worker = PhaseWorker(game_engine, state_repo, registry, notifier=notifier)

    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    # LOBBY - no expiry, no tick
    await worker.tick()

    assert len(notifier.calls) == 0


@pytest.mark.asyncio
async def test_phase_worker_notifier_error_does_not_crash_worker(
    game_engine: GameEngine,
    repositories: tuple[RedisGameStateRepository, ActiveGameRegistry],
) -> None:
    state_repo, registry = repositories

    class ErrorNotifier:
        async def notify_phase_change(
            self, old_state: GameState | None, new_state: GameState
        ) -> None:
            raise RuntimeError("Notification failed")

    worker = PhaseWorker(game_engine, state_repo, registry, notifier=ErrorNotifier())

    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")
    await game_engine.start_game(game_id, "classic_5_6")

    state = await state_repo.get(game_id)
    assert state is not None
    now = datetime.now(timezone.utc)
    state.phase_end_at = now - timedelta(seconds=1)
    await state_repo.save(state)

    # Should not raise
    count = await worker.tick(now=now)
    assert count == 1


def test_should_notify_phase_change_logic() -> None:
    u = uuid4()
    p = [PlayerState(user_id=uuid4(), telegram_id=1, display_name="A")]
    s_night = GameState(
        game_id=u,
        chat_id=u,
        telegram_chat_id=1,
        phase=GamePhase.NIGHT,
        players=p,
        phase_started_at=datetime.now(timezone.utc),
    )
    s_day = GameState(
        game_id=u,
        chat_id=u,
        telegram_chat_id=1,
        phase=GamePhase.DAY,
        players=p,
        phase_started_at=datetime.now(timezone.utc),
    )

    assert _should_notify_phase_change(None, s_night) is True
    assert _should_notify_phase_change(s_night, s_day) is True
    assert _should_notify_phase_change(s_night, s_night) is False
