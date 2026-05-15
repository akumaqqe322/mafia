from dataclasses import dataclass
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


@dataclass(frozen=True)
class DayVoteCallback:
    version: int
    target_telegram_id: int

    def pack(self) -> str:
        return f"dv:{self.version}:{self.target_telegram_id}"

    @classmethod
    def parse(cls, data: str) -> "DayVoteCallback | None":
        if not data.startswith("dv:"):
            return None

        parts = data.split(":")
        if len(parts) != 3:
            return None

        try:
            version = int(parts[1])
            target_id = int(parts[2])
            return cls(version=version, target_telegram_id=target_id)
        except (ValueError, TypeError):
            return None
