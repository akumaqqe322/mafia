import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.bot.services.game_tick import GameTickService, should_notify_phase_change
from app.core.game.engine import GameEngine
from app.core.game.locks import GameLockManager
from app.core.game.schemas import GamePhase, GameState, PlayerState
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository
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
def notifier() -> FakeNotifier:
    return FakeNotifier()

@pytest.fixture
def game_tick_service(
    game_engine: GameEngine,
    repositories: tuple[RedisGameStateRepository, ActiveGameRegistry],
    notifier: FakeNotifier,
) -> GameTickService:
    state_repo, _ = repositories
    return GameTickService(game_engine, state_repo, notifier)

@pytest.mark.asyncio
async def test_admin_finish_game_success(
    game_tick_service: GameTickService,
    game_engine: GameEngine,
    notifier: FakeNotifier,
) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P{i}")
    
    # Move to active phase
    await game_engine.start_game(game_id, "classic_5_6")
    
    old_state = await game_tick_service.state_repository.get(game_id)
    assert old_state is not None
    assert old_state.phase == GamePhase.NIGHT

    # Call admin finish
    new_state = await game_tick_service.admin_finish_game(game_id)
    
    assert new_state is not None
    assert new_state.phase == GamePhase.FINISHED
    assert new_state.winner_side == "admin_stopped"
    
    # Verify notifier call
    assert len(notifier.calls) == 1
    call_old, call_new = notifier.calls[0]
    assert call_old is not None
    assert call_old.phase == GamePhase.NIGHT
    assert call_new.phase == GamePhase.FINISHED

@pytest.mark.asyncio
async def test_admin_finish_game_missing_state(
    game_tick_service: GameTickService,
) -> None:
    result = await game_tick_service.admin_finish_game(uuid4())
    assert result is None

@pytest.mark.asyncio
async def test_admin_finish_game_idempotent(
    game_tick_service: GameTickService,
    game_engine: GameEngine,
    notifier: FakeNotifier,
) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P{i}")
    await game_engine.start_game(game_id, "classic_5_6")

    # First call
    state_after_first = await game_tick_service.admin_finish_game(game_id)
    assert state_after_first is not None
    assert len(notifier.calls) == 1
    
    # Second call
    await game_tick_service.admin_finish_game(game_id)
    # Phase did not change from FINISHED to FINISHED, so no second notification
    assert len(notifier.calls) == 1

def test_should_notify_phase_change_logic() -> None:
    u = uuid4()
    p = [PlayerState(user_id=uuid4(), telegram_id=1, display_name="A")]
    s1 = GameState(
        game_id=u, chat_id=u, telegram_chat_id=1,
        phase=GamePhase.NIGHT, players=p,
        phase_started_at=datetime.now(timezone.utc)
    )
    s2 = GameState(
        game_id=u, chat_id=u, telegram_chat_id=1,
        phase=GamePhase.DAY, players=p,
        phase_started_at=datetime.now(timezone.utc)
    )
    
    assert should_notify_phase_change(None, s1) is True
    assert should_notify_phase_change(s1, s2) is True
    assert should_notify_phase_change(s1, s1) is False
