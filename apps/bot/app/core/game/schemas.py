from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GamePhase(str, Enum):
    LOBBY = "lobby"
    DAY = "day"
    VOTING = "voting"
    NIGHT = "night"
    FINISHED = "finished"


class PlayerState(BaseModel):
    user_id: UUID
    telegram_id: int
    display_name: str
    is_alive: bool = True
    role: str | None = None


class GameSettings(BaseModel):
    min_players: int = 4
    max_players: int = 12
    day_duration_sec: int = 120
    night_duration_sec: int = 60
    voting_duration_sec: int = 60


class GameState(BaseModel):
    game_id: UUID
    chat_id: UUID
    telegram_chat_id: int
    phase: GamePhase = GamePhase.LOBBY
    phase_started_at: datetime
    phase_end_at: datetime | None = None
    players: list[PlayerState] = Field(default_factory=list)
    votes: dict[str, str] = Field(default_factory=dict)
    night_actions: dict[str, dict[str, object]] = Field(default_factory=dict)
    settings: GameSettings = Field(default_factory=GameSettings)
    version: int = 1

    @field_validator("phase_started_at", "phase_end_at")
    @classmethod
    def validate_timezone(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_data: str) -> "GameState":
        return cls.model_validate_json(json_data)
