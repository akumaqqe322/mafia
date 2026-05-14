from datetime import datetime, timezone
from uuid import uuid4

from app.bot.callbacks import LobbyCallback
from app.bot.renderers.lobby import render_lobby
from app.core.game.schemas import GamePhase, GameSettings, GameState, PlayerState


def test_render_lobby() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        settings=GameSettings(),
        players=[
            PlayerState(
                user_id=uuid4(),
                telegram_id=456,
                display_name="Alice",
            ),
            PlayerState(
                user_id=uuid4(),
                telegram_id=789,
                display_name="Bob",
            ),
        ],
    )

    output = render_lobby(state)
    assert "Alice" in output
    assert "Bob" in output
    assert "2/10" in output
    assert "🎮 Mafia Lobby" in output


def test_callback_data_length() -> None:
    # Telegram has 64 byte limit for callback data
    for cb in LobbyCallback:
        assert len(cb.value.encode("utf-8")) <= 64
