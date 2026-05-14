from enum import Enum


class LobbyCallback(str, Enum):
    JOIN = "mg:join"
    LEAVE = "mg:leave"
    START = "mg:start"
    CANCEL = "mg:cancel"
