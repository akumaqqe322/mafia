from datetime import datetime, timezone
from uuid import uuid4

from app.core.game.actions import NightAction, NightActionType, serialize_night_actions
from app.core.game.night_resolver import NightResolver
from app.core.game.roles import RoleId
from app.core.game.schemas import GameState, PlayerState


def test_night_resolver_kill_no_heal() -> None:
    game_id = uuid4()
    p1_id = uuid4()
    p2_id = uuid4()
    p3_id = uuid4()

    state = GameState(
        game_id=game_id,
        chat_id=uuid4(),
        telegram_chat_id=123,
        players=[
            PlayerState(
                user_id=p1_id,
                telegram_id=1,
                display_name="P1",
                role=RoleId.MAFIA.value,
            ),
            PlayerState(
                user_id=p2_id,
                telegram_id=2,
                display_name="P2",
                role=RoleId.CIVILIAN.value,
            ),
            PlayerState(
                user_id=p3_id,
                telegram_id=3,
                display_name="P3",
                role=RoleId.DOCTOR.value,
            ),
        ],
    )

    actions = [
        NightAction(
            actor_user_id=p1_id,
            actor_role=RoleId.MAFIA,
            action_type=NightActionType.KILL,
            target_user_id=p2_id,
            created_at=datetime.now(timezone.utc),
        )
    ]
    state.night_actions = serialize_night_actions(actions)

    result = NightResolver.resolve(state)
    assert result.killed_user_ids == [p2_id]
    assert result.saved_user_ids == []
    # Ensure state not mutated
    assert state.players[1].is_alive is True


def test_night_resolver_kill_with_heal() -> None:
    game_id = uuid4()
    p1_id = uuid4()
    p2_id = uuid4()
    p3_id = uuid4()

    state = GameState(
        game_id=game_id,
        chat_id=uuid4(),
        telegram_chat_id=123,
        players=[
            PlayerState(
                user_id=p1_id,
                telegram_id=1,
                display_name="P1",
                role=RoleId.MAFIA.value,
            ),
            PlayerState(
                user_id=p2_id,
                telegram_id=2,
                display_name="P2",
                role=RoleId.CIVILIAN.value,
            ),
            PlayerState(
                user_id=p3_id,
                telegram_id=3,
                display_name="P3",
                role=RoleId.DOCTOR.value,
            ),
        ],
    )

    actions = [
        NightAction(
            actor_user_id=p1_id,
            actor_role=RoleId.MAFIA,
            action_type=NightActionType.KILL,
            target_user_id=p2_id,
            created_at=datetime.now(timezone.utc),
        ),
        NightAction(
            actor_user_id=p3_id,
            actor_role=RoleId.DOCTOR,
            action_type=NightActionType.HEAL,
            target_user_id=p2_id,
            created_at=datetime.now(timezone.utc),
        ),
    ]
    state.night_actions = serialize_night_actions(actions)

    result = NightResolver.resolve(state)
    assert result.killed_user_ids == []
    assert result.saved_user_ids == [p2_id]


def test_night_resolver_sheriff_check() -> None:
    game_id = uuid4()
    p1_id = uuid4()
    p2_id = uuid4()

    state = GameState(
        game_id=game_id,
        chat_id=uuid4(),
        telegram_chat_id=123,
        players=[
            PlayerState(
                user_id=p1_id,
                telegram_id=1,
                display_name="P1",
                role=RoleId.SHERIFF.value,
            ),
            PlayerState(
                user_id=p2_id,
                telegram_id=2,
                display_name="P2",
                role=RoleId.MAFIA.value,
            ),
        ],
    )

    actions = [
        NightAction(
            actor_user_id=p1_id,
            actor_role=RoleId.SHERIFF,
            action_type=NightActionType.CHECK,
            target_user_id=p2_id,
            created_at=datetime.now(timezone.utc),
        )
    ]
    state.night_actions = serialize_night_actions(actions)

    result = NightResolver.resolve(state)
    assert len(result.checks) == 1
    assert result.checks[0].actor_user_id == p1_id
    assert result.checks[0].target_user_id == p2_id
    assert result.checks[0].is_mafia is True
    assert result.checks[0].target_role == RoleId.MAFIA
