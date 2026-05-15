from dataclasses import dataclass
from enum import Enum

from app.core.game.actions import NightActionType


class LobbyCallback(str, Enum):
    JOIN = "mg:join"
    LEAVE = "mg:leave"
    START = "mg:start"
    CANCEL = "mg:cancel"


@dataclass(frozen=True)
class ParsedNightActionCallback:
    version: int
    action_type: NightActionType
    target_telegram_id: int


class NightActionCallback:
    PREFIX = "na:"

    @classmethod
    def build(cls, version: int, action_type: NightActionType, target_id: int) -> str:
        return f"{cls.PREFIX}{version}:{action_type.value}:{target_id}"

    @classmethod
    def parse(cls, data: str) -> ParsedNightActionCallback | None:
        if not data.startswith(cls.PREFIX):
            return None

        parts = data.split(":")
        if len(parts) != 4:
            return None

        try:
            version = int(parts[1])
            action_type = NightActionType(parts[2])
            target_id = int(parts[3])
            return ParsedNightActionCallback(
                version=version,
                action_type=action_type,
                target_telegram_id=target_id,
            )
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
