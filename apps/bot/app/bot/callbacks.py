from enum import Enum

from app.core.game.actions import NightActionType


class LobbyCallback(str, Enum):
    JOIN = "mg:join"
    LEAVE = "mg:leave"
    START = "mg:start"
    CANCEL = "mg:cancel"


class NightActionCallback:
    PREFIX = "na:"

    @classmethod
    def build(cls, action_type: NightActionType, target_id: int) -> str:
        return f"{cls.PREFIX}{action_type.value}:{target_id}"

    @classmethod
    def parse(cls, data: str) -> tuple[NightActionType, int] | None:
        if not data.startswith(cls.PREFIX):
            return None

        payload = data.removeprefix(cls.PREFIX)
        parts = payload.split(":")
        if len(parts) != 2:
            return None

        try:
            action_type = NightActionType(parts[0])
            target_id = int(parts[1])
            return action_type, target_id
        except (ValueError, TypeError):
            return None
