import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.game.schemas import GamePhase, GameSettings, GameState, PlayerState


def test_game_state_serialization() -> None:
    game_id = uuid4()
    chat_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    player = PlayerState(
        user_id=user_id,
        telegram_id=123456,
        display_name="Test User",
    )

    state = GameState(
        game_id=game_id,
        chat_id=chat_id,
        telegram_chat_id=-100123456789,
        phase=GamePhase.DAY,
        phase_started_at=now,
        players=[player],
        votes={"user1": "user2"},
        version=2,
    )

    # To JSON
    json_data = state.to_json()
    assert isinstance(json_data, str)

    # Check JSON content
    data = json.loads(json_data)
    assert data["game_id"] == str(game_id)
    assert data["phase"] == "day"
    assert data["version"] == 2
    assert data["players"][0]["display_name"] == "Test User"
    assert data["votes"]["user1"] == "user2"

    # From JSON
    new_state = GameState.from_json(json_data)
    assert new_state.game_id == game_id
    # CRITICAL: Verify phase is an enum, not just a string
    assert isinstance(new_state.phase, GamePhase)
    assert new_state.phase == GamePhase.DAY

    assert len(new_state.players) == 1
    assert new_state.players[0].user_id == user_id
    assert new_state.version == 2
    # Check datetime normalization
    assert new_state.phase_started_at.isoformat() == now.isoformat()


def test_timezone_validation() -> None:
    # Valid timezone-aware datetime
    now_utc = datetime.now(timezone.utc)
    GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=now_utc,
    )

    # Invalid naive datetime (no timezone)
    naive_dt = datetime.now()
    with pytest.raises(ValidationError, match="datetime must be timezone-aware"):
        GameState(
            game_id=uuid4(),
            chat_id=uuid4(),
            telegram_chat_id=1,
            phase_started_at=naive_dt,
        )

    # Invalid naive datetime for phase_end_at
    with pytest.raises(ValidationError, match="datetime must be timezone-aware"):
        GameState(
            game_id=uuid4(),
            chat_id=uuid4(),
            telegram_chat_id=1,
            phase_started_at=now_utc,
            phase_end_at=naive_dt,
        )


def test_game_phase_enum() -> None:
    assert GamePhase.LOBBY == "lobby"
    assert GamePhase.DAY == "day"
    assert GamePhase.VOTING == "voting"
    assert GamePhase.NIGHT == "night"
    assert GamePhase.FINISHED == "finished"


def test_default_game_settings() -> None:
    settings = GameSettings()
    assert settings.min_players == 4
    assert settings.max_players == 12


def test_empty_collections() -> None:
    now = datetime.now(timezone.utc)
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=now,
    )
    assert state.players == []
    assert state.votes == {}
    assert state.night_actions == {}

    json_data = state.to_json()
    new_state = GameState.from_json(json_data)
    assert new_state.players == []
    assert new_state.votes == {}
    assert new_state.night_actions == {}
