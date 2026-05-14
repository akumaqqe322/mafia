from uuid import UUID

from pydantic import BaseModel, Field

from app.core.game.schemas import GameState


class DayVoteResolutionResult(BaseModel):
    executed_user_id: UUID | None = None
    vote_counts: dict[UUID, int] = Field(default_factory=dict)
    is_tie: bool = False


class DayVoteResolver:
    @staticmethod
    def resolve(state: GameState) -> DayVoteResolutionResult:
        if not state.votes:
            return DayVoteResolutionResult()

        vote_counts: dict[UUID, int] = {}
        for target_id_str in state.votes.values():
            target_id = UUID(target_id_str)
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1

        if not vote_counts:
            return DayVoteResolutionResult()

        # Find max votes
        max_votes = max(vote_counts.values())
        leaders = [uid for uid, count in vote_counts.items() if count == max_votes]

        if len(leaders) > 1:
            return DayVoteResolutionResult(
                vote_counts=vote_counts,
                is_tie=True,
                executed_user_id=None,
            )

        return DayVoteResolutionResult(
            executed_user_id=leaders[0],
            vote_counts=vote_counts,
            is_tie=False,
        )
