import json
from uuid import UUID, uuid4
from app.core.game.events import GameEvent, GameEventType, EventVisibility

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
        payload={"is_mafia": True}
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
