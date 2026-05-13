from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.game.actions import (
    NightAction,
    NightActionType,
    deserialize_night_actions,
    serialize_night_actions,
)
from app.core.game.roles import RoleId


def test_night_action_creation() -> None:
    actor_id = uuid4()
    target_id = uuid4()
    created_at = datetime.now(timezone.utc)

    action = NightAction(
        actor_user_id=actor_id,
        actor_role=RoleId.MAFIA,
        action_type=NightActionType.KILL,
        target_user_id=target_id,
        created_at=created_at
    )

    assert action.actor_user_id == actor_id
    assert action.actor_role == RoleId.MAFIA
    assert action.action_type == NightActionType.KILL
    assert action.target_user_id == target_id
    assert action.created_at == created_at


def test_night_action_naive_datetime_fails() -> None:
    actor_id = uuid4()
    naive_dt = datetime.now()

    with pytest.raises(ValidationError, match="datetime must be timezone-aware"):
        NightAction(
            actor_user_id=actor_id,
            actor_role=RoleId.MAFIA,
            action_type=NightActionType.KILL,
            target_user_id=uuid4(),
            created_at=naive_dt
        )


def test_serialization_deserialization() -> None:
    actor1 = uuid4()
    actor2 = uuid4()
    target1 = uuid4()

    actions = [
        NightAction(
            actor_user_id=actor1,
            actor_role=RoleId.MAFIA,
            action_type=NightActionType.KILL,
            target_user_id=target1,
            created_at=datetime.now(timezone.utc)
        ),
        NightAction(
            actor_user_id=actor2,
            actor_role=RoleId.DOCTOR,
            action_type=NightActionType.HEAL,
            target_user_id=actor1,
            created_at=datetime.now(timezone.utc)
        )
    ]

    serialized = serialize_night_actions(actions)

    assert len(serialized) == 2
    assert str(actor1) in serialized
    assert str(actor2) in serialized

    deserialized = deserialize_night_actions(serialized)
    assert len(deserialized) == 2

    # Check if data matches
    action1 = next(a for a in deserialized if a.actor_user_id == actor1)
    assert action1.actor_role == RoleId.MAFIA
    assert action1.action_type == NightActionType.KILL
    assert action1.target_user_id == target1


def test_deserialize_empty() -> None:
    assert deserialize_night_actions({}) == []
    assert deserialize_night_actions(None) == []


def test_target_can_be_none() -> None:
    actor_id = uuid4()
    action = NightAction(
        actor_user_id=actor_id,
        actor_role=RoleId.MANIAC,
        action_type=NightActionType.OBSERVE,
        target_user_id=None,
        created_at=datetime.now(timezone.utc)
    )
    assert action.target_user_id is None
