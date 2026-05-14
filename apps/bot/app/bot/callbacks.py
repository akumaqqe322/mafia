from enum import Enum


class LobbyCallback(str, Enum):
    JOIN = "mg:join"
    LEAVE = "mg:leave"
    START = "mg:start"
    CANCEL = "mg:cancel"


class NightActionCallback:
    PREFIX = "na:"

    @classmethod
    def build(cls, action: str, target_id: str) -> str:
        return f"{cls.PREFIX}{action}:{target_id}"
