from enum import Enum
from datetime import datetime
from uuid import UUID
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

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
    role: Optional[str] = None

class GameSettings(BaseModel):
    min_players: int = 4
    max_players: int = 12
    day_duration_sec: int = 120
    night_duration_sec: int = 60
    voting_duration_sec: int = 60

class GameState(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    game_id: UUID
    chat_id: UUID
    telegram_chat_id: int
    phase: GamePhase = GamePhase.LOBBY
    phase_started_at: datetime
    phase_end_at: Optional[datetime] = None
    players: List[PlayerState] = Field(default_factory=list)
    votes: Dict[str, str] = Field(default_factory=dict)
    night_actions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    settings: GameSettings = Field(default_factory=GameSettings)
    version: int = 1

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_data: str) -> "GameState":
        return cls.model_validate_json(json_data)
