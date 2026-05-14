from datetime import datetime, timezone
from uuid import uuid4

from app.bot.callbacks import LobbyCallback
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.renderers.lobby import render_lobby
from app.bot.utils import build_join_url
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
    assert "2/12" in output
    assert "Mode: <i>Auto</i>" in output
    assert "🎭 Mafia Lobby" in output
    # Ensure role is not leaked
    assert "MAFIA" not in output
    assert "CITIZEN" not in output


def test_render_lobby_empty_state() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        settings=GameSettings(),
        players=[],
    )
    output = render_lobby(state)
    assert "Пока никто не присоединился" in output
    assert "0/12" in output


def test_render_lobby_escapes_html() -> None:
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
                display_name="<b>Evil</b>",
            ),
        ],
    )
    output = render_lobby(state)
    assert "&lt;b&gt;Evil&lt;/b&gt;" in output
    assert "<b>Evil</b>" not in output


def test_callback_data_length() -> None:
    # Telegram has 64 byte limit for callback data
    for cb in LobbyCallback:
        assert len(cb.value.encode("utf-8")) <= 64


def test_build_join_url_and_payload() -> None:
    token = "abcdefgh12345678"  # typical urlsafe token
    url = build_join_url("my_bot", token)
    assert url == f"https://t.me/my_bot?start=join_{token}"
    # Payload is "join_..."
    payload = f"join_{token}"
    assert len(payload.encode("utf-8")) <= 64


def test_lobby_keyboard_uses_url() -> None:
    kb = build_lobby_keyboard(invite_url="https://example.com")
    # In aiogram 3, we can inspect inline_keyboard
    first_row = kb.inline_keyboard[0]
    join_button = first_row[0]
    assert join_button.text == "Join ✅"
    assert join_button.url == "https://example.com"
    assert join_button.callback_data is None
