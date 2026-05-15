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


class AdminAction(str, Enum):
    REFRESH = "refresh"
    TICK = "tick"
    FINISH = "finish"
    CONFIRM_FINISH = "confirm_finish"
    KICK_LIST = "klist"
    KICK = "kick"
    BACK = "back"


@dataclass(frozen=True)
class AdminCallback:
    action: AdminAction
    version: int | None = None
    target_telegram_id: int | None = None

    def pack(self) -> str:
        if self.action in (AdminAction.REFRESH, AdminAction.BACK):
            return f"adm:{self.action.value}"
        if self.action == AdminAction.KICK:
            return f"adm:{self.action.value}:{self.version}:{self.target_telegram_id}"
        return f"adm:{self.action.value}:{self.version}"

    @classmethod
    def parse(cls, data: str) -> "AdminCallback | None":
        if not data.startswith("adm:"):
            return None

        parts = data.split(":")

        try:
            action = AdminAction(parts[1])
        except (IndexError, ValueError):
            return None

        if action in (AdminAction.REFRESH, AdminAction.BACK):
            if len(parts) != 2:
                return None
            return cls(action=action)

        if action in (
            AdminAction.TICK,
            AdminAction.FINISH,
            AdminAction.CONFIRM_FINISH,
            AdminAction.KICK_LIST,
        ):
            if len(parts) != 3:
                return None
            try:
                return cls(action=action, version=int(parts[2]))
            except ValueError:
                return None

        if action == AdminAction.KICK:
            if len(parts) != 4:
                return None
            try:
                return cls(action=action, version=int(parts[2]), target_telegram_id=int(parts[3]))
            except ValueError:
                return None

        return None
