from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.game.events import EventVisibility, GameEvent, GameEventType
from app.core.game.schemas import GameState


def test_game_event_defaults_event_id() -> None:
    event = GameEvent(
        type=GameEventType.NIGHT_NO_DEATHS,
        visibility=EventVisibility.PUBLIC,
    )
    assert event.event_id is not None
    assert isinstance(event.event_id, UUID)


def test_game_event_payload_default_is_independent() -> None:
    event1 = GameEvent(
        type=GameEventType.NIGHT_NO_DEATHS,
        visibility=EventVisibility.PUBLIC,
    )
    event2 = GameEvent(
        type=GameEventType.NIGHT_NO_DEATHS,
        visibility=EventVisibility.PUBLIC,
    )

    event1.payload["key"] = "value"
    assert "key" not in event2.payload


def test_game_event_related_user_ids_default_is_independent() -> None:
    event1 = GameEvent(
        type=GameEventType.DAY_VOTE_TIE,
        visibility=EventVisibility.PUBLIC,
    )
    event2 = GameEvent(
        type=GameEventType.DAY_VOTE_TIE,
        visibility=EventVisibility.PUBLIC,
    )

    u1 = uuid4()
    event1.related_user_ids.append(u1)
    assert u1 not in event2.related_user_ids


def test_game_event_serializes_enums_as_values() -> None:
    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
    )
    dump = event.model_dump(mode="json")
    assert dump["type"] == "check_result"
    assert dump["visibility"] == "private"


def test_private_check_result_event_shape() -> None:
    recipient_id = uuid4()
    target_id = uuid4()
    event = GameEvent(
        type=GameEventType.CHECK_RESULT,
        visibility=EventVisibility.PRIVATE,
        recipient_user_id=recipient_id,
        target_user_id=target_id,
        payload={"is_mafia": True},
    )
    assert event.type == GameEventType.CHECK_RESULT
    assert event.visibility == EventVisibility.PRIVATE
    assert event.recipient_user_id == recipient_id
    assert event.target_user_id == target_id
    assert event.payload["is_mafia"] is True


def test_public_day_vote_tie_event_shape() -> None:
    u1 = uuid4()
    u2 = uuid4()
    event = GameEvent(
        type=GameEventType.DAY_VOTE_TIE,
        visibility=EventVisibility.PUBLIC,
        related_user_ids=[u1, u2],
    )
    assert event.type == GameEventType.DAY_VOTE_TIE
    assert event.visibility == EventVisibility.PUBLIC
    assert len(event.related_user_ids) == 2
    assert u1 in event.related_user_ids
    assert u2 in event.related_user_ids


def test_game_state_last_events_default_empty() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    assert state.last_events == []


def test_game_state_last_events_default_is_independent() -> None:
    state1 = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=1,
        phase_started_at=datetime.now(timezone.utc),
    )
    state2 = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=2,
        phase_started_at=datetime.now(timezone.utc),
    )

    event = GameEvent(
        type=GameEventType.NIGHT_NO_DEATHS,
        visibility=EventVisibility.PUBLIC,
    )
    state1.last_events.append(event)

    assert len(state1.last_events) == 1
    assert len(state2.last_events) == 0


def test_game_state_accepts_last_events() -> None:
    event = GameEvent(
        type=GameEventType.DAY_PLAYER_EXECUTED,
        visibility=EventVisibility.PUBLIC,
        target_user_id=uuid4(),
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        last_events=[event],
    )
    assert len(state.last_events) == 1
    assert state.last_events[0].type == GameEventType.DAY_PLAYER_EXECUTED


def test_game_state_last_events_serializes_to_json() -> None:
    event = GameEvent(
        type=GameEventType.DAY_VOTE_TIE,
        visibility=EventVisibility.PUBLIC,
        related_user_ids=[uuid4(), uuid4()],
    )
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        last_events=[event],
    )

    dump = state.model_dump(mode="json")
    assert "last_events" in dump
    assert len(dump["last_events"]) == 1
    assert dump["last_events"][0]["type"] == "day_vote_tie"
    assert dump["last_events"][0]["visibility"] == "public"
    assert len(dump["last_events"][0]["related_user_ids"]) == 2


def test_game_state_backward_compatible_without_last_events() -> None:
    # Simulating loading from old Redis data (no last_events key)
    data = {
        "game_id": str(uuid4()),
        "chat_id": str(uuid4()),
        "telegram_chat_id": 123,
        "phase": "lobby",
        "phase_started_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }
    state = GameState.model_validate(data)
    assert state.last_events == []


def test_game_state_voting_message_id_default_none() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
    )
    assert state.voting_message_id is None


def test_game_state_accepts_voting_message_id() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        voting_message_id=456,
    )
    assert state.voting_message_id == 456


def test_game_state_voting_message_id_serializes_to_json() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
        phase_started_at=datetime.now(timezone.utc),
        voting_message_id=789,
    )
    dump = state.model_dump(mode="json")
    assert dump["voting_message_id"] == 789


def test_game_state_backward_compatible_without_voting_message_id() -> None:
    data = {
        "game_id": str(uuid4()),
        "chat_id": str(uuid4()),
        "telegram_chat_id": 111,
        "phase": "lobby",
        "phase_started_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }
    state = GameState.model_validate(data)
    assert state.voting_message_id is None
