from datetime import datetime, timezone
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bot.callbacks import DayVoteCallback, LobbyCallback, NightActionCallback
from app.bot.keyboards.day_vote import build_day_vote_keyboard, get_available_day_vote_targets
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.keyboards.night_action import (
    build_night_action_keyboard,
    get_available_night_targets,
)
from app.bot.presets import select_preset_for_players
from app.bot.renderers.check_result import render_check_result
from app.bot.renderers.day_vote import render_day_vote_started
from app.bot.renderers.day_vote_result import render_day_vote_result
from app.bot.renderers.game import render_game_started
from app.bot.renderers.lobby import render_lobby
from app.bot.renderers.night_action import render_night_action_dm
from app.bot.renderers.phase import (
    get_newly_dead_players,
    render_day_started,
    render_game_finished,
    render_night_started,
    render_voting_started,
)
from app.bot.renderers.role import render_role_dm
from app.bot.services import (
    MAX_MAFIA_CHAT_MESSAGE_LENGTH,
    can_manage_game,
    can_receive_mafia_chat,
    can_send_mafia_chat,
    get_mafia_chat_recipients,
    is_group_admin,
    is_lobby_creator,
    is_mafia_chat_phase,
    render_mafia_chat_message,
    validate_mafia_chat_text,
)
from app.bot.utils import build_join_url
from app.core.game.actions import NightActionType
from app.core.game.events import EventVisibility, GameEvent, GameEventType
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
                role=RoleId.CIVILIAN.value,
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
    assert buttons[0].callback_data == NightActionCallback.build(NightActionType.KILL, 789)

    # Doctor heal action (can heal self)
    kb = build_night_action_keyboard(state, actor, NightActionType.HEAL)
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(buttons) == 2


def test_night_action_callback_encoding_length() -> None:
    # Test that na:<action_type>:<telegram_id> matches 64 bytes
    # telegram_id can be up to 64 bits (up to 20 digits)
    cb_data = NightActionCallback.build(NightActionType.PROTECT, 12345678901234567890)
    assert len(cb_data.encode("utf-8")) <= 64


def test_night_action_callback_build_parse_valid() -> None:
    cb_data = NightActionCallback.build(NightActionType.KILL, 123456789)
    assert cb_data == "na:kill:123456789"
    parsed = NightActionCallback.parse(cb_data)
    assert parsed == (NightActionType.KILL, 123456789)


def test_night_action_callback_parse_invalid() -> None:
    assert NightActionCallback.parse("invalid") is None
    assert NightActionCallback.parse("na:invalid:123") is None
    assert NightActionCallback.parse("na:kill:abc") is None


def test_available_targets_mafia_kill_excludes_teammates() -> None:
    alice_id = uuid4()
    bob_id = uuid4()  # another mafia
    charlie_id = uuid4()  # citizen
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
                telegram_id=1,
                display_name="A",
                role=RoleId.MAFIA.value,
            ),
            PlayerState(
                user_id=bob_id,
                telegram_id=2,
                display_name="B",
                role=RoleId.DON.value,
            ),
            PlayerState(
                user_id=charlie_id,
                telegram_id=3,
                display_name="C",
                role=RoleId.CIVILIAN.value,
            ),
        ],
    )
    actor = state.players[0]
    targets = get_available_night_targets(state, actor, NightActionType.KILL)
    assert len(targets) == 1
    assert targets[0].display_name == "C"


def test_available_targets_doctor_can_heal_self() -> None:
    alice_id = uuid4()
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
                telegram_id=1,
                display_name="A",
                role=RoleId.DOCTOR.value,
            ),
        ],
    )
    actor = state.players[0]
    targets = get_available_night_targets(state, actor, NightActionType.HEAL)
    assert len(targets) == 1
    assert targets[0].user_id == alice_id


def test_get_newly_dead_players_detects_deaths() -> None:
    u1, u2, u3 = uuid4(), uuid4(), uuid4()
    old_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=u1, telegram_id=1, display_name="A", is_alive=True),
            PlayerState(user_id=u2, telegram_id=2, display_name="B", is_alive=True),
            PlayerState(user_id=u3, telegram_id=3, display_name="C", is_alive=False),
        ],
    )
    new_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(
                user_id=u1, telegram_id=1, display_name="A", is_alive=False
            ),  # newly dead
            PlayerState(user_id=u2, telegram_id=2, display_name="B", is_alive=True),
            PlayerState(
                user_id=u3, telegram_id=3, display_name="C", is_alive=False
            ),  # was already dead
        ],
    )
    dead = get_newly_dead_players(old_state, new_state)
    assert len(dead) == 1
    assert dead[0].user_id == u1


def test_get_newly_dead_players_no_deaths() -> None:
    u1 = uuid4()
    old_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=u1, telegram_id=1, display_name="A", is_alive=True)
        ],
    )
    new_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(user_id=u1, telegram_id=1, display_name="A", is_alive=True)
        ],
    )
    assert len(get_newly_dead_players(old_state, new_state)) == 0


def test_render_day_started_with_deaths_escapes_names() -> None:
    u1 = uuid4()
    old_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(
                user_id=u1, telegram_id=1, display_name="<Evil>", is_alive=True
            )
        ],
    )
    new_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(
                user_id=u1, telegram_id=1, display_name="<Evil>", is_alive=False
            )
        ],
    )
    output = render_day_started(old_state, new_state)
    assert "☀️ Наступил день" in output
    assert "&lt;Evil&gt;" in output
    assert "<Evil>" not in output


def test_render_day_started_no_deaths() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(
                user_id=uuid4(), telegram_id=1, display_name="A", is_alive=True
            )
        ],
    )
    output = render_day_started(state, state)
    assert "без потерь" in output


def test_render_day_started_does_not_reveal_roles() -> None:
    u1 = uuid4()
    old_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(
                user_id=u1,
                telegram_id=1,
                display_name="A",
                is_alive=True,
                role="mafia",
            )
        ],
    )
    new_state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            PlayerState(
                user_id=u1,
                telegram_id=1,
                display_name="A",
                is_alive=False,
                role="mafia",
            )
        ],
    )
    output = render_day_started(old_state, new_state)
    assert "mafia" not in output
    assert "Мафия" not in output


def test_render_night_started_contains_phase_text() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
    )
    output = render_night_started(state)
    assert "🌙 Наступила ночь" in output
    assert "инструкции в личные сообщения" in output


def test_render_voting_started_contains_phase_text() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
    )
    output = render_voting_started(state)
    assert "⚖️ Началось голосование" in output


def test_render_game_finished_shows_winner_side() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        winner_side="mafia",
        players=[],
    )
    output = render_game_finished(state)
    assert "🏁 Игра окончена" in output
    assert "mafia" in output


def test_render_game_finished_lists_alive_and_dead_players() -> None:
    u1, u2 = uuid4(), uuid4()
    p1 = make_player(
        role=RoleId.CIVILIAN.value,
        display_name="Alice",
        is_alive=True,
    )
    p1.user_id = u1
    p2 = make_player(
        role=RoleId.MAFIA.value,
        display_name="Bob",
        is_alive=False,
    )
    p2.user_id = u2

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        winner_side="civilian",
        players=[p1, p2],
    )

    output = render_game_finished(state)
    assert "Выжившие" in output
    assert "Alice" in output
    assert "Выбывшие" in output
    assert "Bob" in output


def test_render_game_finished_reveals_roles_after_finish() -> None:
    p1 = make_player(
        role=RoleId.SHERIFF.value,
        display_name="Alice",
        is_alive=True,
    )
    p2 = make_player(
        role=RoleId.MAFIA.value,
        display_name="Bob",
        is_alive=False,
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        winner_side="civilian",
        players=[p1, p2],
    )

    output = render_game_finished(state)
    assert "Шериф" in output
    assert "Мафия" in output


def test_render_game_finished_handles_empty_sections() -> None:
    p1 = make_player(
        role=RoleId.CIVILIAN.value,
        display_name="Alice",
        is_alive=True,
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[p1],
    )
    output = render_game_finished(state)
    assert "Выбывшие" in output
    assert "— нет" in output


def test_render_game_finished_escapes_player_names() -> None:
    p1 = make_player(None, display_name="<script>Alice</script>")
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[p1],
    )
    output = render_game_finished(state)
    assert "&lt;script&gt;Alice&lt;/script&gt;" in output
    assert "<script>" not in output


def test_render_game_finished_handles_unknown_role() -> None:
    p1 = make_player(role="broken_role", display_name="Alice")
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[p1],
    )
    output = render_game_finished(state)
    assert "роль неизвестна" in output
    assert "broken_role" not in output


def test_render_game_finished_does_not_reveal_ids() -> None:
    uid = uuid4()
    p1 = make_player(role=RoleId.MAFIA.value, display_name="Alice")
    p1.user_id = uid
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[p1],
    )
    output = render_game_finished(state)
    assert str(uid) not in output
    assert str(state.game_id) not in output
    assert str(state.chat_id) not in output


def make_player(
    role: str | None,
    is_alive: bool = True,
    telegram_id: int = 1,
    display_name: str = "Player",
) -> PlayerState:
    return PlayerState(
        user_id=uuid4(),
        telegram_id=telegram_id,
        display_name=display_name,
        role=role,
        is_alive=is_alive,
    )


def test_can_send_mafia_chat() -> None:
    assert can_send_mafia_chat(make_player(RoleId.MAFIA.value, is_alive=True)) is True
    assert can_send_mafia_chat(make_player(RoleId.DON.value, is_alive=True)) is True
    assert can_send_mafia_chat(make_player(RoleId.MAFIA.value, is_alive=False)) is False
    assert can_send_mafia_chat(make_player(RoleId.DON.value, is_alive=False)) is False
    assert can_send_mafia_chat(make_player(RoleId.LAWYER.value, is_alive=True)) is False
    assert can_send_mafia_chat(make_player(RoleId.CIVILIAN.value, is_alive=True)) is False
    assert can_send_mafia_chat(make_player(None, is_alive=True)) is False
    assert can_send_mafia_chat(make_player("unknown", is_alive=True)) is False


def test_can_receive_mafia_chat() -> None:
    assert (
        can_receive_mafia_chat(make_player(RoleId.MAFIA.value, is_alive=True)) is True
    )
    assert (
        can_receive_mafia_chat(make_player(RoleId.MAFIA.value, is_alive=False)) is True
    )
    assert can_receive_mafia_chat(make_player(RoleId.DON.value, is_alive=True)) is True
    assert (
        can_receive_mafia_chat(make_player(RoleId.DON.value, is_alive=False)) is True
    )
    assert (
        can_receive_mafia_chat(make_player(RoleId.LAWYER.value, is_alive=True)) is False
    )
    assert (
        can_receive_mafia_chat(make_player(RoleId.CIVILIAN.value, is_alive=True))
        is False
    )


def test_get_mafia_chat_recipients() -> None:
    p1 = make_player(RoleId.MAFIA.value, telegram_id=1, display_name="M1")
    p2 = make_player(RoleId.MAFIA.value, telegram_id=2, display_name="M2", is_alive=False)
    p3 = make_player(RoleId.DON.value, telegram_id=3, display_name="D")
    p4 = make_player(RoleId.LAWYER.value, telegram_id=4, display_name="L")
    p5 = make_player(RoleId.CIVILIAN.value, telegram_id=5, display_name="C")

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.NIGHT,
        phase_started_at=datetime.now(timezone.utc),
        players=[p1, p2, p3, p4, p5],
    )

    # Sender M1 (alive)
    recipients = get_mafia_chat_recipients(state, p1)
    assert len(recipients) == 2
    assert {r.telegram_id for r in recipients} == {2, 3}

    # Sender M2 (dead)
    recipients = get_mafia_chat_recipients(state, p2)
    assert len(recipients) == 0

    # Sender D (alive)
    recipients = get_mafia_chat_recipients(state, p3)
    assert len(recipients) == 2
    assert {r.telegram_id for r in recipients} == {1, 2}


def test_validate_mafia_chat_text() -> None:
    assert validate_mafia_chat_text(" Hello ") == "Hello"
    assert validate_mafia_chat_text("   ") is None
    assert validate_mafia_chat_text("") is None
    assert validate_mafia_chat_text("A" * (MAX_MAFIA_CHAT_MESSAGE_LENGTH + 1)) is None
    assert validate_mafia_chat_text("A" * MAX_MAFIA_CHAT_MESSAGE_LENGTH) is not None


def test_render_mafia_chat_message() -> None:
    sender = make_player(RoleId.MAFIA.value, display_name="<b>Alice</b>")
    text = "Kill <Bob> & survive!"
    output = render_mafia_chat_message(sender, text)

    assert "💬 Сообщение от <b>&lt;b&gt;Alice&lt;/b&gt;</b>:" in output
    assert "Kill &lt;Bob&gt; &amp; survive!" in output
    # Ensure role is not leaked
    assert "Мафия" not in output
    assert RoleId.MAFIA.value not in output


def test_is_mafia_chat_phase() -> None:
    assert is_mafia_chat_phase(GamePhase.NIGHT) is True
    assert is_mafia_chat_phase(GamePhase.DAY) is True
    assert is_mafia_chat_phase(GamePhase.VOTING) is True
    assert is_mafia_chat_phase(GamePhase.LOBBY) is False
    assert is_mafia_chat_phase(GamePhase.FINISHED) is False


def test_is_lobby_creator() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        creator_telegram_id=111,
    )
    assert is_lobby_creator(state, 111) is True
    assert is_lobby_creator(state, 222) is False


def test_is_lobby_creator_none() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        creator_telegram_id=None,
    )
    assert is_lobby_creator(state, 111) is False


class FakeChatMember:
    def __init__(self, status: str) -> None:
        self.status = status


class FakeBot:
    def __init__(self, status: str | None = None, should_fail: bool = False) -> None:
        self.status = status
        self.should_fail = should_fail

    async def get_chat_member(self, chat_id: int, user_id: int) -> FakeChatMember:
        if self.should_fail:
            # We use a mock-like behavior since constructor requires method/message
            raise TelegramAPIError(method=MagicMock(), message="boom")
        return FakeChatMember(self.status or "member")


@pytest.mark.asyncio
async def test_is_group_admin_true() -> None:
    bot = cast(Bot, FakeBot(status="creator"))
    assert await is_group_admin(bot, 123, 111) is True

    bot = cast(Bot, FakeBot(status="administrator"))
    assert await is_group_admin(bot, 123, 111) is True


@pytest.mark.asyncio
async def test_is_group_admin_false() -> None:
    bot = cast(Bot, FakeBot(status="member"))
    assert await is_group_admin(bot, 123, 111) is False


@pytest.mark.asyncio
async def test_is_group_admin_error() -> None:
    bot = cast(Bot, FakeBot(should_fail=True))
    assert await is_group_admin(bot, 123, 111) is False


@pytest.mark.asyncio
async def test_can_manage_game_creator() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        creator_telegram_id=111,
    )
    bot = cast(Bot, FakeBot(status="member"))  # Not admin, but creator
    assert await can_manage_game(bot, state, 111) is True


@pytest.mark.asyncio
async def test_can_manage_game_admin() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        creator_telegram_id=222,
    )
    bot = cast(Bot, FakeBot(status="administrator"))  # Admin, but not creator
    assert await can_manage_game(bot, state, 111) is True


@pytest.mark.asyncio
async def test_can_manage_game_denied() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase=GamePhase.LOBBY,
        phase_started_at=datetime.now(timezone.utc),
        creator_telegram_id=222,
    )
    bot = cast(Bot, FakeBot(status="member"))  # Neither admin nor creator
    assert await can_manage_game(bot, state, 111) is False


def test_day_vote_callback_pack() -> None:
    cb = DayVoteCallback(target_telegram_id=123)
    assert cb.pack() == "dv:123"


def test_day_vote_callback_parse_valid() -> None:
    cb = DayVoteCallback.parse("dv:123456")
    assert cb is not None
    assert cb.target_telegram_id == 123456


def test_day_vote_callback_parse_invalid() -> None:
    assert DayVoteCallback.parse("invalid") is None
    assert DayVoteCallback.parse("dv:abc") is None
    assert DayVoteCallback.parse("na:kill:123") is None


def test_day_vote_callback_size_safe() -> None:
    # 20 digits is max for 64-bit int
    cb = DayVoteCallback(target_telegram_id=12345678901234567890)
    assert len(cb.pack().encode("utf-8")) <= 64


def test_get_available_day_vote_targets() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            make_player(None, telegram_id=1, display_name="Alice", is_alive=True),
            make_player(None, telegram_id=2, display_name="Bob", is_alive=False),
            make_player(None, telegram_id=3, display_name="Charlie", is_alive=True),
        ],
    )

    # All targets (only alive)
    targets = get_available_day_vote_targets(state)
    assert len(targets) == 2
    assert {t.telegram_id for t in targets} == {1, 3}

    # Exclude voter
    targets = get_available_day_vote_targets(state, voter_telegram_id=1)
    assert len(targets) == 1
    assert targets[0].telegram_id == 3


def test_build_day_vote_keyboard_contains_alive_players() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            make_player(None, telegram_id=1, display_name="Alice", is_alive=True),
            make_player(None, telegram_id=2, display_name="Bob", is_alive=False),
        ],
    )
    kb = build_day_vote_keyboard(state)
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(buttons) == 1
    assert buttons[0].text == "Alice"
    assert buttons[0].callback_data == "dv:1"


def test_render_day_vote_started_contains_expected_text() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
        players=[
            make_player(None, is_alive=True),
            make_player(None, is_alive=True),
            make_player(None, is_alive=False),
        ],
    )
    output = render_day_vote_started(state)
    assert "Голосование началось" in output
    assert "Живых игроков: 2" in output
    # Ensure role is not revealed
    assert "Мафия" not in output
    assert "mafia" not in output


def test_render_day_vote_result_executed() -> None:
    target_id = uuid4()
    p_target = make_player(
        role=RoleId.MAFIA.value,
        display_name="Alice",
        telegram_id=100,
    )
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.DAY_PLAYER_EXECUTED,
        visibility=EventVisibility.PUBLIC,
        target_user_id=target_id,
        payload={"votes_count": 3},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
        last_events=[event],
    )

    text = render_day_vote_result(state)
    assert text is not None
    assert "Голосование завершено" in text
    assert "Alice" in text
    assert "покидает игру" in text
    assert "Голосов: 3" in text
    # Safety: do not reveal role
    assert "Мафия" not in text
    assert RoleId.MAFIA.value not in text


def test_render_day_vote_result_tie() -> None:
    u1, u2 = uuid4(), uuid4()
    p1 = make_player(None, display_name="Alice")
    p1.user_id = u1
    p2 = make_player(None, display_name="Bob")
    p2.user_id = u2

    event = GameEvent(
        type=GameEventType.DAY_VOTE_TIE,
        visibility=EventVisibility.PUBLIC,
        related_user_ids=[u1, u2],
        payload={"votes_count": 2},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p1, p2],
        last_events=[event],
    )

    text = render_day_vote_result(state)
    assert text is not None
    assert "Голоса разделились между" in text
    assert "Alice" in text
    assert "Bob" in text
    assert "никто не покинул город" in text
    assert "Голосов у лидеров: 2" in text


def test_render_day_vote_result_no_votes() -> None:
    event = GameEvent(
        type=GameEventType.DAY_VOTE_NO_VOTES,
        visibility=EventVisibility.PUBLIC,
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        last_events=[event],
    )

    text = render_day_vote_result(state)
    assert text is not None
    assert "так и не пришёл к решению" in text
    assert "никто не покинул город" in text


def test_render_day_vote_result_returns_none_without_vote_event() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        last_events=[],
    )
    assert render_day_vote_result(state) is None


def test_render_day_vote_result_escapes_player_names() -> None:
    target_id = uuid4()
    p_target = make_player(None, display_name="<script>Alice</script>")
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.DAY_PLAYER_EXECUTED,
        visibility=EventVisibility.PUBLIC,
        target_user_id=target_id,
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
        last_events=[event],
    )

    text = render_day_vote_result(state)
    assert text is not None
    assert "&lt;script&gt;Alice&lt;/script&gt;" in text
    assert "<script>" not in text


def test_render_day_vote_result_does_not_reveal_ids() -> None:
    target_id = uuid4()
    p_target = make_player(None, display_name="Alice")
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.DAY_PLAYER_EXECUTED,
        visibility=EventVisibility.PUBLIC,
        target_user_id=target_id,
        payload={"votes_count": 3},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
        last_events=[event],
    )

    text = render_day_vote_result(state)
    assert text is not None
    assert str(target_id) not in text
    assert str(state.game_id) not in text
    assert str(state.chat_id) not in text


def test_render_check_result_mafia_positive() -> None:
    target_id = uuid4()
    p_target = make_player(role=RoleId.MAFIA.value, display_name="Alice")
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        target_user_id=target_id,
        payload={"is_mafia": True, "target_role": RoleId.MAFIA.value},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
    )

    text = render_check_result(state, event)
    assert text is not None
    assert "Результат проверки" in text
    assert "Alice" in text
    assert "связан с мафией" in text
    # Safety: do not reveal exact role
    assert RoleId.MAFIA.value not in text.lower()


def test_render_check_result_mafia_negative() -> None:
    target_id = uuid4()
    p_target = make_player(role=RoleId.CIVILIAN.value, display_name="Bob")
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        target_user_id=target_id,
        payload={"is_mafia": False, "target_role": RoleId.CIVILIAN.value},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
    )

    text = render_check_result(state, event)
    assert text is not None
    assert "не связан с мафией" in text
    assert "Bob" in text


def test_render_check_result_returns_none_for_non_check_event() -> None:
    event = GameEvent(
        type=GameEventType.DAY_VOTE_NO_VOTES,
        visibility=EventVisibility.PUBLIC,
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    assert render_check_result(state, event) is None


def test_render_check_result_returns_none_for_public_event() -> None:
    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PUBLIC,
        target_user_id=uuid4(),
        payload={"is_mafia": True},
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    assert render_check_result(state, event) is None


def test_render_check_result_returns_none_without_target() -> None:
    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        payload={"is_mafia": True},
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    assert render_check_result(state, event) is None


def test_render_check_result_returns_none_with_invalid_payload() -> None:
    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        target_user_id=uuid4(),
        payload={"is_mafia": "yes"},
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    assert render_check_result(state, event) is None


def test_render_check_result_escapes_player_name() -> None:
    target_id = uuid4()
    p_target = make_player(None, display_name="<script>Alice</script>")
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        target_user_id=target_id,
        payload={"is_mafia": False},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
    )

    text = render_check_result(state, event)
    assert text is not None
    assert "&lt;script&gt;Alice&lt;/script&gt;" in text
    assert "<script>" not in text


def test_render_check_result_does_not_reveal_ids_or_roles() -> None:
    target_id = uuid4()
    p_target = make_player(role=RoleId.MAFIA.value, display_name="Alice")
    p_target.user_id = target_id

    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        target_user_id=target_id,
        payload={"is_mafia": True, "target_role": RoleId.MAFIA.value},
    )

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        players=[p_target],
    )

    text = render_check_result(state, event)
    assert text is not None
    assert str(target_id) not in text
    assert str(state.game_id) not in text
    assert str(state.chat_id) not in text
    # Ensure role ID value is not leaked
    assert RoleId.MAFIA.value not in text.lower()
