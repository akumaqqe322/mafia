from uuid import uuid4
from datetime import datetime, timezone
from app.core.game.victory import VictoryConditionService, WinnerSide
from app.core.game.schemas import GameState, PlayerState
from app.core.game.roles import RoleId


def test_victory_civilians_win() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=uuid4(), telegram_id=1, display_name="P1", role=RoleId.CIVILIAN.value),
            PlayerState(user_id=uuid4(), telegram_id=2, display_name="P2", role=RoleId.MAFIA.value, is_alive=False),
            PlayerState(user_id=uuid4(), telegram_id=3, display_name="P3", role=RoleId.SHERIFF.value),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.CIVILIANS
    assert result.reason == "all_threats_eliminated"
    assert len(result.winning_player_ids) == 2


def test_victory_mafia_win_parity() -> None:
    p1 = uuid4()
    p2 = uuid4()
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=p1, telegram_id=1, display_name="P1", role=RoleId.CIVILIAN.value),
            PlayerState(user_id=p2, telegram_id=2, display_name="P2", role=RoleId.MAFIA.value),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.MAFIA
    assert result.reason == "mafia_parity"
    assert p2 in result.winning_player_ids


def test_victory_maniac_win() -> None:
    maniac_id = uuid4()
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=uuid4(), telegram_id=1, display_name="P1", role=RoleId.CIVILIAN.value),
            PlayerState(user_id=uuid4(), telegram_id=2, display_name="P2", role=RoleId.MAFIA.value, is_alive=False),
            PlayerState(user_id=maniac_id, telegram_id=3, display_name="P3", role=RoleId.MANIAC.value),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.MANIAC
    assert result.reason == "maniac_last_threat"
    assert maniac_id in result.winning_player_ids


def test_victory_draw_all_dead() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=uuid4(), telegram_id=1, display_name="P1", role=RoleId.CIVILIAN.value, is_alive=False),
            PlayerState(user_id=uuid4(), telegram_id=2, display_name="P2", role=RoleId.MAFIA.value, is_alive=False),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.DRAW


def test_victory_none_continues() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=uuid4(), telegram_id=1, display_name="P1", role=RoleId.CIVILIAN.value),
            PlayerState(user_id=uuid4(), telegram_id=2, display_name="P2", role=RoleId.CIVILIAN.value),
            PlayerState(user_id=uuid4(), telegram_id=3, display_name="P3", role=RoleId.MAFIA.value),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.NONE


def test_victory_lawyer_is_mafia() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=uuid4(), telegram_id=1, display_name="P1", role=RoleId.CIVILIAN.value),
            PlayerState(user_id=uuid4(), telegram_id=2, display_name="P2", role=RoleId.LAWYER.value),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.MAFIA


def test_victory_hobo_is_town() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=uuid4(), telegram_id=1, display_name="P1", role=RoleId.HOBO.value),
            PlayerState(user_id=uuid4(), telegram_id=2, display_name="P2", role=RoleId.MAFIA.value, is_alive=False),
        ]
    )
    result = VictoryConditionService.check(state)
    assert result.winner_side == WinnerSide.CIVILIANS
