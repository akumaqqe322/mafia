from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.game.actions import NightActionType, deserialize_night_actions
from app.core.game.engine import (
    GameAlreadyExistsError,
    GameEngine,
    GameFullError,
    GameNotFoundError,
    InvalidGamePhaseError,
    InvalidNightActionError,
    InvalidVoteError,
    NotEnoughPlayersError,
    PlayerAlreadyInGameError,
    PlayerNotAliveError,
    PlayerNotInGameError,
)
from app.core.game.locks import GameLockManager
from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase, GameSettings
from app.core.game.victory import WinnerSide
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
    active_id = await game_engine.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )
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
    assert (
        await game_engine.active_game_registry.get_active_game_by_chat(tg_chat_id)
        is None
    )


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
async def test_advance_phase_finished_noop(game_engine: GameEngine) -> None:
    game_id = uuid4()
    state = await game_engine.create_game(game_id, uuid4(), 123)

    # Manual transition to FINISHED
    state.phase = GamePhase.FINISHED
    version = state.version
    await game_engine.state_repository.save(state)

    # Should be no-op
    new_state = await game_engine.advance_phase(game_id)
    assert new_state.phase == GamePhase.FINISHED
    assert new_state.version == version


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
        target.user_id,
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
        game_id,
        mafia.user_id,
        NightActionType.KILL,
        targets[0].user_id,
    )

    # Submit second (change target)
    state = await game_engine.submit_night_action(
        game_id,
        mafia.user_id,
        NightActionType.KILL,
        targets[1].user_id,
    )

    actions = deserialize_night_actions(state.night_actions)
    assert len(actions) == 1
    assert actions[0].target_user_id == targets[1].user_id
    assert state.version == 9


@pytest.mark.asyncio
async def test_submit_night_action_invalid_role_mismatch(
    game_engine: GameEngine,
) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    # Patient (Civilian) cannot kill
    civ = next(p for p in state.players if p.role == RoleId.CIVILIAN.value)

    with pytest.raises(InvalidNightActionError, match="not allowed for role"):
        await game_engine.submit_night_action(
            game_id,
            civ.user_id,
            NightActionType.KILL,
            uuid4(),
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
            game_id,
            uuid4(),
            NightActionType.KILL,
            uuid4(),
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
            game_id,
            mafia.user_id,
            NightActionType.KILL,
            uuid4(),
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
            game_id,
            uuid4(),
            NightActionType.KILL,
            uuid4(),
        )

    # Dead target
    target = next(p for p in state.players if p.user_id != mafia.user_id)
    target.is_alive = False
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidNightActionError, match="Target .* is dead"):
        await game_engine.submit_night_action(
            game_id,
            mafia.user_id,
            NightActionType.KILL,
            target.user_id,
        )

    with pytest.raises(InvalidNightActionError, match="Target .* not in game"):
        await game_engine.submit_night_action(
            game_id,
            mafia.user_id,
            NightActionType.KILL,
            uuid4(),
        )


@pytest.mark.asyncio
async def test_submit_night_action_requires_target(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)

    with pytest.raises(InvalidNightActionError, match="requires a target"):
        await game_engine.submit_night_action(
            game_id,
            mafia.user_id,
            NightActionType.KILL,
            None,
        )


@pytest.mark.asyncio
async def test_submit_night_action_unknown_actor_role(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    # Manually set broken role
    p = state.players[0]
    p.role = "broken_role"
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidNightActionError, match="has invalid role"):
        await game_engine.submit_night_action(
            game_id,
            p.user_id,
            NightActionType.KILL,
            uuid4(),
        )


@pytest.mark.asyncio
async def test_resolve_night_success_kill(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)
    target = next(p for p in state.players if p.user_id != mafia.user_id)

    # Submit kill
    await game_engine.submit_night_action(
        game_id, mafia.user_id, NightActionType.KILL, target.user_id
    )

    result = await game_engine.resolve_night(game_id)

    assert result.killed_user_ids == [target.user_id]

    # Verify state mutation
    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    target_player = next(p for p in state.players if p.user_id == target.user_id)
    assert target_player.is_alive is False
    assert state.night_actions == {}
    assert state.version == 9


@pytest.mark.asyncio
async def test_resolve_night_saved_by_heal(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), 1000 + i, f"P {i}")

    state = await game_engine.start_game(game_id, "classic_5_6")

    mafia = next(p for p in state.players if p.role == RoleId.MAFIA.value)
    doctor = next(p for p in state.players if p.role == RoleId.DOCTOR.value)
    target = next(
        p for p in state.players if p.user_id not in (mafia.user_id, doctor.user_id)
    )

    # Mafia kills
    await game_engine.submit_night_action(
        game_id, mafia.user_id, NightActionType.KILL, target.user_id
    )
    # Doctor heals
    await game_engine.submit_night_action(
        game_id, doctor.user_id, NightActionType.HEAL, target.user_id
    )

    result = await game_engine.resolve_night(game_id)

    assert result.killed_user_ids == []
    assert result.saved_user_ids == [target.user_id]

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    target_player = next(p for p in state.players if p.user_id == target.user_id)
    assert target_player.is_alive is True


@pytest.mark.asyncio
async def test_resolve_night_invalid_phase(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)

    with pytest.raises(InvalidGamePhaseError):
        await game_engine.resolve_night(game_id)


@pytest.mark.asyncio
async def test_submit_day_vote_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p1_id = uuid4()
    p2_id = uuid4()
    await game_engine.join_game(game_id, p1_id, 1, "P1")
    await game_engine.join_game(game_id, p2_id, 2, "P2")
    for i in range(3):
        await game_engine.join_game(game_id, uuid4(), 100 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")
    # Night -> Day
    await game_engine.advance_phase(game_id)
    # Day -> Voting
    state = await game_engine.advance_phase(game_id)
    assert state.phase == GamePhase.VOTING

    state = await game_engine.submit_day_vote(game_id, p1_id, p2_id)
    assert state.votes[str(p1_id)] == str(p2_id)
    assert state.version == 9


@pytest.mark.asyncio
async def test_submit_day_vote_replace(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p1_id = uuid4()
    p2_id = uuid4()
    p3_id = uuid4()
    await game_engine.join_game(game_id, p1_id, 1, "P1")
    await game_engine.join_game(game_id, p2_id, 2, "P2")
    await game_engine.join_game(game_id, p3_id, 3, "P3")
    for i in range(2):
        await game_engine.join_game(game_id, uuid4(), 100 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    await game_engine.advance_phase(game_id)

    await game_engine.submit_day_vote(game_id, p1_id, p2_id)
    state = await game_engine.submit_day_vote(game_id, p1_id, p3_id)
    assert state.votes[str(p1_id)] == str(p3_id)
    assert len(state.votes) == 1


@pytest.mark.asyncio
async def test_submit_day_vote_invalid_self_vote(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p1_id = uuid4()
    await game_engine.join_game(game_id, p1_id, 1, "P1")
    for i in range(4):
        await game_engine.join_game(game_id, uuid4(), 100 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    await game_engine.advance_phase(game_id)

    with pytest.raises(InvalidVoteError, match="cannot vote for themselves"):
        await game_engine.submit_day_vote(game_id, p1_id, p1_id)


@pytest.mark.asyncio
async def test_submit_day_vote_invalid_phase(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p1_id = uuid4()
    p2_id = uuid4()
    await game_engine.join_game(game_id, p1_id, 1, "P1")
    await game_engine.join_game(game_id, p2_id, 2, "P2")

    # Still in LOBBY
    with pytest.raises(InvalidGamePhaseError):
        await game_engine.submit_day_vote(game_id, p1_id, p2_id)


@pytest.mark.asyncio
async def test_resolve_day_votes_success(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    players: list[UUID] = []
    for i in range(5):
        uid = uuid4()
        players.append(uid)
        await game_engine.join_game(game_id, uid, i, f"P{i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    await game_engine.advance_phase(game_id)

    # 3 votes for p0
    await game_engine.submit_day_vote(game_id, players[1], players[0])
    await game_engine.submit_day_vote(game_id, players[2], players[0])
    await game_engine.submit_day_vote(game_id, players[3], players[0])

    result = await game_engine.resolve_day_votes(game_id)
    assert result.executed_user_id == players[0]
    assert result.is_tie is False

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    player0 = next(p for p in state.players if p.user_id == players[0])
    assert player0.is_alive is False
    assert state.votes == {}


@pytest.mark.asyncio
async def test_resolve_day_votes_tie(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    players: list[UUID] = []
    for i in range(5):
        uid = uuid4()
        players.append(uid)
        await game_engine.join_game(game_id, uid, i, f"P{i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    await game_engine.advance_phase(game_id)

    # 1 vote for p0, 1 vote for p1
    await game_engine.submit_day_vote(game_id, players[2], players[0])
    await game_engine.submit_day_vote(game_id, players[3], players[1])

    result = await game_engine.resolve_day_votes(game_id)
    assert result.executed_user_id is None
    assert result.is_tie is True

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert all(p.is_alive for p in state.players)
    assert state.votes == {}


@pytest.mark.asyncio
async def test_resolve_night_victory_mafia(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p_mafia = uuid4()
    p_civ1 = uuid4()
    p_civ2 = uuid4()
    players = [p_mafia, p_civ1, p_civ2]
    roles = [RoleId.MAFIA, RoleId.CIVILIAN, RoleId.CIVILIAN]

    for i, (p_id, role) in enumerate(zip(players, roles)):
        await game_engine.join_game(game_id, p_id, i, f"P{i}")

    # Manually start game to control roles
    async with game_engine.lock_manager.lock(game_id):
        state = await game_engine.state_repository.get(game_id)
        assert state is not None
        for i, player in enumerate(state.players):
            player.role = roles[i].value
        state.phase = GamePhase.NIGHT
        state.phase_started_at = datetime.now(timezone.utc)
        await game_engine.state_repository.save(state)

    # Mafia kills civ1 -> 1 mafia vs 1 civ -> Parity
    await game_engine.submit_night_action(game_id, p_mafia, NightActionType.KILL, p_civ1)
    await game_engine.resolve_night(game_id)

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.phase == GamePhase.FINISHED
    assert state.winner_side == WinnerSide.MAFIA.value


@pytest.mark.asyncio
async def test_resolve_day_votes_victory_civilians(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p_mafia = uuid4()
    p_civ1 = uuid4()
    p_civ2 = uuid4()
    players = [p_mafia, p_civ1, p_civ2]
    roles = [RoleId.MAFIA, RoleId.CIVILIAN, RoleId.CIVILIAN]

    for i, (p_id, role) in enumerate(zip(players, roles)):
        await game_engine.join_game(game_id, p_id, i, f"P{i}")

    async with game_engine.lock_manager.lock(game_id):
        state = await game_engine.state_repository.get(game_id)
        assert state is not None
        for i, player in enumerate(state.players):
            player.role = roles[i].value
        state.phase = GamePhase.VOTING
        state.phase_started_at = datetime.now(timezone.utc)
        await game_engine.state_repository.save(state)

    # Civilians execute mafia
    await game_engine.submit_day_vote(game_id, p_civ1, p_mafia)
    await game_engine.submit_day_vote(game_id, p_civ2, p_mafia)

    await game_engine.resolve_day_votes(game_id)

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.phase == GamePhase.FINISHED
    assert state.winner_side == WinnerSide.CIVILIANS.value


@pytest.mark.asyncio
async def test_submit_day_vote_dead_voter(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p1_id = uuid4()
    p2_id = uuid4()
    await game_engine.join_game(game_id, p1_id, 1, "P1")
    await game_engine.join_game(game_id, p2_id, 2, "P2")
    for i in range(3):
        await game_engine.join_game(game_id, uuid4(), 100 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    state = await game_engine.advance_phase(game_id)
    assert state.phase == GamePhase.VOTING

    # Manually kill p1
    voter = next(p for p in state.players if p.user_id == p1_id)
    voter.is_alive = False
    await game_engine.state_repository.save(state)

    with pytest.raises(PlayerNotAliveError):
        await game_engine.submit_day_vote(game_id, p1_id, p2_id)


@pytest.mark.asyncio
async def test_submit_day_vote_invalid_target(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    p1_id = uuid4()
    p2_id = uuid4()
    await game_engine.join_game(game_id, p1_id, 1, "P1")
    await game_engine.join_game(game_id, p2_id, 2, "P2")
    for i in range(3):
        await game_engine.join_game(game_id, uuid4(), 100 + i, f"P {i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    state = await game_engine.advance_phase(game_id)
    assert state.phase == GamePhase.VOTING

    # Target not in game
    with pytest.raises(InvalidVoteError, match="not in game"):
        await game_engine.submit_day_vote(game_id, p1_id, uuid4())

    # Target is dead
    target = next(p for p in state.players if p.user_id == p2_id)
    target.is_alive = False
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidVoteError, match="is dead"):
        await game_engine.submit_day_vote(game_id, p1_id, p2_id)


@pytest.mark.asyncio
async def test_resolve_day_votes_no_votes(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), i, f"P{i}")

    await game_engine.start_game(game_id, "classic_5_6")
    await game_engine.advance_phase(game_id)
    await game_engine.advance_phase(game_id)

    result = await game_engine.resolve_day_votes(game_id)
    assert result.executed_user_id is None
    assert result.is_tie is False

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.votes == {}


@pytest.mark.asyncio
async def test_resolve_day_votes_invalid_phase(game_engine: GameEngine) -> None:
    game_id = uuid4()
    await game_engine.create_game(game_id, uuid4(), 123)
    for i in range(5):
        await game_engine.join_game(game_id, uuid4(), i, f"P{i}")

    await game_engine.start_game(game_id, "classic_5_6")

    # Still in NIGHT
    with pytest.raises(InvalidGamePhaseError):
        await game_engine.resolve_day_votes(game_id)


@pytest.mark.asyncio
async def test_submit_night_action_finished_error(game_engine: GameEngine) -> None:
    game_id = uuid4()
    state = await game_engine.create_game(game_id, uuid4(), 123)
    state.phase = GamePhase.FINISHED
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidGamePhaseError):
        await game_engine.submit_night_action(
            game_id, uuid4(), NightActionType.KILL, uuid4()
        )


@pytest.mark.asyncio
async def test_submit_day_vote_finished_error(game_engine: GameEngine) -> None:
    game_id = uuid4()
    state = await game_engine.create_game(game_id, uuid4(), 123)
    state.phase = GamePhase.FINISHED
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidGamePhaseError):
        await game_engine.submit_day_vote(game_id, uuid4(), uuid4())


@pytest.mark.asyncio
async def test_resolve_night_finished_error(game_engine: GameEngine) -> None:
    game_id = uuid4()
    state = await game_engine.create_game(game_id, uuid4(), 123)
    state.phase = GamePhase.FINISHED
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidGamePhaseError):
        await game_engine.resolve_night(game_id)


@pytest.mark.asyncio
async def test_resolve_day_votes_finished_error(game_engine: GameEngine) -> None:
    game_id = uuid4()
    state = await game_engine.create_game(game_id, uuid4(), 123)
    state.phase = GamePhase.FINISHED
    await game_engine.state_repository.save(state)

    with pytest.raises(InvalidGamePhaseError):
        await game_engine.resolve_day_votes(game_id)


@pytest.mark.asyncio
async def test_registry_is_clean_after_night_victory(game_engine: GameEngine) -> None:
    game_id = uuid4()
    tg_chat_id = 123
    await game_engine.create_game(game_id, uuid4(), tg_chat_id)

    p_mafia = uuid4()
    p_civ1 = uuid4()
    p_civ2 = uuid4()
    players = [p_mafia, p_civ1, p_civ2]
    roles = [RoleId.MAFIA, RoleId.CIVILIAN, RoleId.CIVILIAN]

    for i, (p_id, role) in enumerate(zip(players, roles)):
        await game_engine.join_game(game_id, p_id, i, f"P{i}")

    # Manually start game to control roles
    async with game_engine.lock_manager.lock(game_id):
        state = await game_engine.state_repository.get(game_id)
        assert state is not None
        for i, player in enumerate(state.players):
            player.role = roles[i].value
        state.phase = GamePhase.NIGHT
        state.phase_started_at = datetime.now(timezone.utc)
        await game_engine.state_repository.save(state)

    # Mafia kills civ1 -> 1 mafia vs 1 civ -> Parity
    await game_engine.submit_night_action(
        game_id, p_mafia, NightActionType.KILL, p_civ1
    )
    await game_engine.resolve_night(game_id)

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.phase == GamePhase.FINISHED

    # Check registry is clean
    active_id = await game_engine.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )
    assert active_id is None

    active_games = await game_engine.active_game_registry.list_active_games()
    assert game_id not in active_games


@pytest.mark.asyncio
async def test_registry_is_clean_after_day_victory(game_engine: GameEngine) -> None:
    game_id = uuid4()
    tg_chat_id = 123
    await game_engine.create_game(game_id, uuid4(), tg_chat_id)

    p_mafia = uuid4()
    p_civ1 = uuid4()
    p_civ2 = uuid4()
    players = [p_mafia, p_civ1, p_civ2]
    roles = [RoleId.MAFIA, RoleId.CIVILIAN, RoleId.CIVILIAN]

    for i, (p_id, role) in enumerate(zip(players, roles)):
        await game_engine.join_game(game_id, p_id, i, f"P{i}")

    async with game_engine.lock_manager.lock(game_id):
        state = await game_engine.state_repository.get(game_id)
        assert state is not None
        for i, player in enumerate(state.players):
            player.role = roles[i].value
        state.phase = GamePhase.VOTING
        state.phase_started_at = datetime.now(timezone.utc)
        await game_engine.state_repository.save(state)

    # Civilians execute mafia
    await game_engine.submit_day_vote(game_id, p_civ1, p_mafia)
    await game_engine.submit_day_vote(game_id, p_civ2, p_mafia)

    await game_engine.resolve_day_votes(game_id)

    state = await game_engine.state_repository.get(game_id)
    assert state is not None
    assert state.phase == GamePhase.FINISHED

    # Check registry is clean
    active_id = await game_engine.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )
    assert active_id is None

    active_games = await game_engine.active_game_registry.list_active_games()
    assert game_id not in active_games


@pytest.mark.asyncio
async def test_create_game_after_previous_finished(game_engine: GameEngine) -> None:
    game_id1 = uuid4()
    tg_chat_id = 123
    await game_engine.create_game(game_id1, uuid4(), tg_chat_id)

    # Add mafia and win immediately via resolve_night (1 player left)
    p_mafia = uuid4()
    await game_engine.join_game(game_id1, p_mafia, 1, "Mafia")

    # Manually start as NIGHT and role MAFIA
    async with game_engine.lock_manager.lock(game_id1):
        state = await game_engine.state_repository.get(game_id1)
        assert state is not None
        state.players[0].role = RoleId.MAFIA.value
        state.phase = GamePhase.NIGHT
        await game_engine.state_repository.save(state)

    await game_engine.resolve_night(game_id1)

    # Now create new game in same chat
    game_id2 = uuid4()
    state2 = await game_engine.create_game(game_id2, uuid4(), tg_chat_id)
    assert state2.game_id == game_id2

    active_id = await game_engine.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )
    assert active_id == game_id2


@pytest.mark.asyncio
async def test_resolve_day_votes_unknown_game(game_engine: GameEngine) -> None:
    with pytest.raises(GameNotFoundError):
        await game_engine.resolve_day_votes(uuid4())
