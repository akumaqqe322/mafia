from uuid import uuid4

from app.core.game.day_resolver import DayVoteResolver
from app.core.game.schemas import GameState


def test_day_resolver_no_votes() -> None:
    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
    )
    result = DayVoteResolver.resolve(state)
    assert result.executed_user_id is None
    assert result.is_tie is False
    assert result.vote_counts == {}


def test_day_resolver_single_winner() -> None:
    p1_id = uuid4()
    p2_id = uuid4()
    p3_id = uuid4()

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
    )
    # p1 and p3 vote for p2
    state.votes = {
        str(p1_id): str(p2_id),
        str(p3_id): str(p2_id),
    }

    result = DayVoteResolver.resolve(state)
    assert result.executed_user_id == p2_id
    assert result.is_tie is False
    assert result.vote_counts == {p2_id: 2}


def test_day_resolver_tie() -> None:
    p1_id = uuid4()
    p2_id = uuid4()
    p3_id = uuid4()
    p4_id = uuid4()

    state = GameState(
        game_id=uuid4(),
        chat_id=uuid4(),
        telegram_chat_id=123,
    )
    # p1 votes for p2
    # p3 votes for p4
    state.votes = {
        str(p1_id): str(p2_id),
        str(p3_id): str(p4_id),
    }

    result = DayVoteResolver.resolve(state)
    assert result.executed_user_id is None
    assert result.is_tie is True
    assert result.vote_counts == {p2_id: 1, p4_id: 1}
