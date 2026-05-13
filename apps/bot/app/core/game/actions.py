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
    """Serializes a list of night actions into a dictionary where the key is the actor's user ID."""
    return {str(a.actor_user_id): a.model_dump(mode="json") for a in actions}


def deserialize_night_actions(
    data: dict[str, dict[str, object]] | None,
) -> list[NightAction]:
    """Deserializes a dictionary of night actions into a list of NightAction objects."""
    if not data:
        return []
    return [NightAction.model_validate(val) for val in data.values()]
