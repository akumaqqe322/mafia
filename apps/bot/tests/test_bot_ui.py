from datetime import datetime, timezone
from uuid import uuid4

from app.bot.callbacks import LobbyCallback
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.keyboards.night_action import build_night_action_keyboard
from app.bot.presets import select_preset_for_players
from app.bot.renderers.game import render_game_started
from app.bot.renderers.lobby import render_lobby
from app.bot.renderers.role import render_role_dm
from app.bot.renderers.night_action import render_night_action_dm
from app.bot.utils import build_join_url
from app.core.game.actions import NightActionType
from app.core.game.roles import PresetRegistry, RoleId, RoleRegistry
from app.core.game.schemas import GamePhase, GameSettings, GameState, PlayerState


def test_select_preset_for_supported_count() -> None:
    # 5-6 is classic
    assert select_preset_for_players(5) == "classic_5_6"
    assert select_preset_for_players(6) == "classic_5_6"
    # 9-10 is classic
    assert select_preset_for_players(10) == "classic_9_10"
    # 11-12 is extended
    assert select_preset_for_players(12) == "extended_11_12"


def test_select_preset_returns_none_for_too_few_players() -> None:
    assert select_preset_for_players(1) is None
    assert select_preset_for_players(4) is None


def test_select_preset_returns_existing_preset() -> None:
    result = select_preset_for_players(5)
    assert result is not None
    preset = PresetRegistry.get_by_id(result)
    assert preset.min_players <= 5 <= preset.max_players


def test_render_role_dm_contains_role_metadata() -> None:
    role_id = RoleId.MAFIA
    metadata = RoleRegistry.get(role_id)
    output = render_role_dm(role_id)
    assert metadata.name in output
    assert metadata.emoji in output
    assert metadata.description in output


def test_render_role_dm_contains_night_instruction() -> None:
    output = render_role_dm(RoleId.DOCTOR)
    assert "Сейчас ночь" in output
    assert "Не раскрывай свою роль" in output


def test_render_game_started_does_not_reveal_roles() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.NIGHT,
        phase_started_at=datetime.now(timezone.utc),
        settings=GameSettings(),
        players=[
            PlayerState(
                user_id=uuid4(),
                telegram_id=456,
                display_name="Alice",
                role=RoleId.MAFIA.value,
            ),
        ],
    )
    output = render_game_started(state)
    assert "Мафия" not in output
    assert "🕵️‍♂️" not in output
    assert "Игра началась" in output
    assert "Ночь" in output


def test_render_game_started_contains_player_count() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.NIGHT,
        phase_started_at=datetime.now(timezone.utc),
        settings=GameSettings(),
        players=[PlayerState(user_id=uuid4(), telegram_id=1, display_name="A")] * 7,
    )
    output = render_game_started(state)
    assert "Игроков в игре: 7" in output


def test_render_game_started_dm_failed_message() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.NIGHT,
        phase_started_at=datetime.now(timezone.utc),
        settings=GameSettings(),
        players=[PlayerState(user_id=uuid4(), telegram_id=1, display_name="A")],
    )
    output = render_game_started(state, dm_failed=True)
    assert "не удалось отправить" in output
    # Ensure role names are not in output
    assert "Мафия" not in output
    assert "Мирный" not in output


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


def test_render_night_action_dm() -> None:
    output = render_night_action_dm(NightActionType.KILL)
    assert "Выберите цель" in output
    assert "🔫" in output


def test_build_night_action_keyboard() -> None:
    alice_id = uuid4()
    bob_id = uuid4()
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.NIGHT,
        phase_started_at=datetime.now(timezone.utc),
        settings=GameSettings(),
        players=[
            PlayerState(
                user_id=alice_id,
                telegram_id=456,
                display_name="Alice",
                role=RoleId.MAFIA.value,
            ),
            PlayerState(
                user_id=bob_id,
                telegram_id=789,
                display_name="Bob",
            ),
        ],
    )
    actor = state.players[0]  # Alice

    # Mafia kill action
    kb = build_night_action_keyboard(state, actor, NightActionType.KILL)
    # Alice should see Bob but NOT herself
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(buttons) == 1
    assert buttons[0].text == "Bob"
    assert buttons[0].callback_data == f"na:kill:{bob_id}"

    # Doctor heal action (can heal self)
    kb = build_night_action_keyboard(state, actor, NightActionType.HEAL)
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(buttons) == 2
    display_names = [b.text for b in buttons]
    assert "Alice" in display_names
    assert "Bob" in display_names


def test_night_action_callback_encoding_length() -> None:
    # Test that na:<action>:<uuid> is within 64 bytes
    target_id = uuid4()
    cb_data = f"na:kill:{target_id}"
    assert len(cb_data.encode("utf-8")) <= 64
