from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.game.roles import RoleId


class NightActionType(str, Enum):
    KILL = "kill"
    HEAL = "heal"
    CHECK = "check"
    BLOCK = "block"
    PROTECT = "protect"
    OBSERVE = "observe"


class NightAction(BaseModel):
    actor_user_id: UUID
    actor_role: RoleId
    action_type: NightActionType
    target_user_id: UUID | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return v


def serialize_night_actions(
    actions: list[NightAction],
) -> dict[str, dict[str, object]]:
    """Serializes a list of night actions into a dictionary where the key is the
    actor's user ID."""
    return {str(a.actor_user_id): a.model_dump(mode="json") for a in actions}


def deserialize_night_actions(
    data: dict[str, dict[str, object]] | None,
) -> list[NightAction]:
    """Deserializes a dictionary of night actions into a list of NightAction objects."""
    if not data:
        return []
    return [NightAction.model_validate(val) for val in data.values()]


def get_allowed_night_actions(role: RoleId) -> set[NightActionType]:
    """Returns a set of allowed night action types for a given role."""
    mapping: dict[RoleId, set[NightActionType]] = {
        RoleId.MAFIA: {NightActionType.KILL},
        RoleId.DON: {NightActionType.CHECK},
        RoleId.SHERIFF: {NightActionType.CHECK},
        RoleId.DOCTOR: {NightActionType.HEAL},
        RoleId.MANIAC: {NightActionType.KILL},
        RoleId.LOVER: {NightActionType.BLOCK},
        RoleId.LAWYER: {NightActionType.PROTECT},
        RoleId.HOBO: {NightActionType.OBSERVE},
    }
    return mapping.get(role, set())


def night_action_requires_target(action_type: NightActionType) -> bool:
    """Returns True if the night action type requires a target player."""
    # All current actions require a target
    return action_type in {
        NightActionType.KILL,
        NightActionType.HEAL,
        NightActionType.CHECK,
        NightActionType.BLOCK,
        NightActionType.PROTECT,
        NightActionType.OBSERVE,
    }
