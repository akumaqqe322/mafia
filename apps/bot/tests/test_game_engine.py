from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.game.engine import (
    GameAlreadyExistsError,
    GameEngine,
    GameFullError,
    GameNotFoundError,
    InvalidGamePhaseError,
    InvalidNightActionError,
    PlayerNotAliveError,
    NotEnoughPlayersError,
    PlayerAlreadyInGameError,
    PlayerNotInGameError,
)
from app.core.game.locks import GameLockManager
from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase, GameSettings
from app.core.game.actions import NightActionType, deserialize_night_actions
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import (
    RedisGameStateRepository,
)
from tests.fakes.redis import FakeRedisClient


@pytest.fixture
def fake_redis() -> FakeRedisClient:
    return FakeRedisClient()


@pytest.fixture
def game_engine(fake_redis: FakeRedisClient) -> GameEngine:
    state_repo = RedisGameStateRepository(fake_redis)
    registry = ActiveGameRegistry(fake_redis)
    lock_manager = GameLockManager()
    return GameEngine(state_repo, registry, lock_manager)


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


@pytest.mark.asyncio
async def test_start_game_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)

    # Add 5 players for classic_5_6
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"Player {i}")
    state = await game_engine.start_game(game_id, "classic_5_6")

    assert state.phase == GamePhase.NIGHT
    assert state.phase_end_at is not None
    assert state.phase_started_at is not None
    assert state.phase_end_at > state.phase_started_at

    duration = (state.phase_end_at - state.phase_started_at).total_seconds()
    assert abs(duration - state.settings.night_duration_sec) < 0.1

    assert all(p.role is not None for p in state.players)

    roles = [p.role for p in state.players]
    assert roles.count(RoleId.MAFIA.value) == 1
    assert roles.count(RoleId.SHERIFF.value) == 1
    assert roles.count(RoleId.DOCTOR.value) == 1
    assert roles.count(RoleId.CIVILIAN.value) == 2
    assert state.version == 7


@pytest.mark.asyncio
async def test_start_game_not_enough_players(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    await game_engine.join_game(game_id, uuid4(), 456, "P1")

    with pytest.raises(NotEnoughPlayersError):
        await game_engine.start_game(game_id, "classic_5_6")


@pytest.mark.asyncio
async def test_start_game_invalid_phase(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)

    # Start it once (effectively, though we need players)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")
    await game_engine.start_game(game_id, "classic_5_6")

    # Try starting again while in NIGHT phase
    with pytest.raises(InvalidGamePhaseError):
        await game_engine.start_game(game_id, "classic_5_6")


@pytest.mark.asyncio
async def test_start_game_not_found(game_engine: GameEngine) -> None:
    with pytest.raises(GameNotFoundError):
        await game_engine.start_game(uuid4(), "classic_5_6")


@pytest.mark.asyncio
async def test_advance_phase_flow(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    # Starts in LOBBY -> Start Game -> NIGHT
    state = await game_engine.start_game(game_id, "classic_5_6")
    assert state.phase == GamePhase.NIGHT
    assert state.version == 7

    # NIGHT -> DAY
    state = await game_engine.advance_phase(game_id)
    assert state.phase == GamePhase.DAY
    assert state.version == 8
    assert state.phase_end_at is not None
    assert state.phase_started_at is not None
    duration = (state.phase_end_at - state.phase_started_at).total_seconds()
    assert abs(duration - state.settings.day_duration_sec) < 0.1

    # DAY -> VOTING
    state = await game_engine.advance_phase(game_id)
    assert state.phase == GamePhase.VOTING
    assert state.version == 9
    assert state.phase_end_at is not None
    assert state.phase_started_at is not None
    duration = (state.phase_end_at - state.phase_started_at).total_seconds()
    assert abs(duration - state.settings.voting_duration_sec) < 0.1

    # VOTING -> NIGHT
    state = await game_engine.advance_phase(game_id)
    assert state.phase == GamePhase.NIGHT
    assert state.version == 10
    assert state.phase_end_at is not None
    assert state.phase_started_at is not None
    duration = (state.phase_end_at - state.phase_started_at).total_seconds()
    assert abs(duration - state.settings.night_duration_sec) < 0.1


@pytest.mark.asyncio
async def test_advance_phase_invalid_lobby(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)

    with pytest.raises(InvalidGamePhaseError, match="Cannot advance from lobby"):
        await game_engine.advance_phase(game_id)


@pytest.mark.asyncio
async def test_advance_phase_invalid_finished(game_engine: GameEngine) -> None:
    game_id = uuid4()
    state = await game_engine.create_game(game_id, uuid4(), 123)

    # Manual transition to FINISHED
    state.phase = GamePhase.FINISHED
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidGamePhaseError, match="Cannot advance from finished"):
        await game_engine.advance_phase(game_id)


@pytest.mark.asyncio
async def test_advance_phase_not_found(game_engine: GameEngine) -> None:
    with pytest.raises(GameNotFoundError):
        await game_engine.advance_phase(uuid4())


@pytest.mark.asyncio
async def test_submit_night_action_success_mafia(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    # Find mafia player
    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)
    # Find any other target
    target = next(p for p in state.players if p.user_id != mafia.user_id)

    state = await game_engine.submit_night_action(
        game_id,
        mafia.user_id,
        NightActionType.KILL,
        target.user_id
    )

    actions = deserialize_night_actions(state.night_actions)
    assert len(actions) == 1
    assert actions[0].actor_user_id == mafia.user_id
    assert actions[0].action_type == NightActionType.KILL
    assert actions[0].target_user_id == target.user_id
    assert state.version == 8


@pytest.mark.asyncio
async def test_submit_night_action_replace(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)
    targets = [p for p in state.players if p.user_id != mafia.user_id]

    # Submit first
    await game_engine.submit_night_action(
        game_id, mafia.user_id, NightActionType.KILL, targets[0].user_id
    )

    # Submit second (change target)
    state = await game_engine.submit_night_action(
        game_id, mafia.user_id, NightActionType.KILL, targets[1].user_id
    )

    actions = deserialize_night_actions(state.night_actions)
    assert len(actions) == 1
    assert actions[0].target_user_id == targets[1].user_id
    assert state.version == 9


@pytest.mark.asyncio
async def test_submit_night_action_invalid_role_mismatch(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    # Patient (Civilian) cannot kill
    civ = next(p for p in state.players if p.role == RoleId.CIVILIAN.value)

    with pytest.raises(InvalidNightActionError, match="not allowed for role"):
        await game_engine.submit_night_action(
            game_id, civ.user_id, NightActionType.KILL, uuid4()
        )


@pytest.mark.asyncio
async def test_submit_night_action_invalid_phase(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    # Still in LOBBY
    with pytest.raises(InvalidGamePhaseError):
        await game_engine.submit_night_action(
            game_id, uuid4(), NightActionType.KILL, uuid4()
        )


@pytest.mark.asyncio
async def test_submit_night_action_dead_actor(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)
    # Manually kill mafia
    mafia.is_alive = False
    await game_engine.state_repository.save(state)

    with pytest.raises(PlayerNotAliveError):
        await game_engine.submit_night_action(
            game_id, mafia.user_id, NightActionType.KILL, uuid4()
        )


@pytest.mark.asyncio
async def test_submit_night_action_invalid_target(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)

    # Actor not in game
    with pytest.raises(PlayerNotInGameError):
        await game_engine.submit_night_action(
            game_id, uuid4(), NightActionType.KILL, uuid4()
        )

    # Dead target
    target = next(p for p in state.players if p.user_id != mafia.user_id)
    target.is_alive = False
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidNightActionError, match="Target .* is dead"):
        await game_engine.submit_night_action(
            game_id, mafia.user_id, NightActionType.KILL, target.user_id
        )

    # Target not in game
    with pytest.raises(InvalidNightActionError, match="Target .* not in game"):
        await game_engine.submit_night_action(
            game_id, mafia.user_id, NightActionType.KILL, uuid4()
        )
