from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class GameEventType(str, Enum):
    NIGHT_PLAYER_KILLED = "night_player_killed"
    NIGHT_NO_DEATHS = "night_no_deaths"
    DAY_PLAYER_EXECUTED = "day_player_executed"
    DAY_VOTE_TIE = "day_vote_tie"
    DAY_VOTE_NO_VOTES = "day_vote_no_votes"
    CHECK_RESULT = "check_result"
    GAME_FINISHED = "game_finished"

class EventVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    TEAM = "team"
    INTERNAL = "internal"

GameEventPayloadValue = str | int | bool | None
GameEventPayload = dict[str, GameEventPayloadValue]

class GameEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    type: GameEventType
    visibility: EventVisibility

    recipient_user_id: UUID | None = None
    actor_user_id: UUID | None = None
    target_user_id: UUID | None = None
    related_user_ids: list[UUID] = Field(default_factory=list)

    payload: GameEventPayload = Field(default_factory=dict)
