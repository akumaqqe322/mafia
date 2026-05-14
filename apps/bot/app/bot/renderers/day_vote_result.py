import html
from uuid import UUID

from app.core.game.events import EventVisibility, GameEventType
from app.core.game.schemas import GameState


def _find_player_name(state: GameState, user_id: UUID) -> str:
    """Finds a player by user_id and returns their escaped display name."""
    player = next((p for p in state.players if p.user_id == user_id), None)
    if player:
        return html.escape(player.display_name)
    return "неизвестный игрок"


def render_day_vote_result(state: GameState) -> str | None:
    """
    Renders the public result of the day voting phase.
    Returns None if no relevant public day vote event is found.
    """
    vote_event = next(
        (
            e
            for e in state.last_events
            if e.visibility == EventVisibility.PUBLIC
            and e.type
            in (
                GameEventType.DAY_PLAYER_EXECUTED,
                GameEventType.DAY_VOTE_TIE,
                GameEventType.DAY_VOTE_NO_VOTES,
            )
        ),
        None,
    )

    if not vote_event:
        return None

    header = "⚖️ <b>Голосование завершено.</b>\n\n"

    if vote_event.type == GameEventType.DAY_PLAYER_EXECUTED:
        if not vote_event.target_user_id:
            return None
        name = _find_player_name(state, vote_event.target_user_id)
        votes_count = vote_event.payload.get("votes_count")

        text = f"{header}Город сделал выбор: <b>{name}</b>.\nИгрок покидает игру."
        if isinstance(votes_count, int):
            text += f"\n\nГолосов: {votes_count}"
        return text

    if vote_event.type == GameEventType.DAY_VOTE_TIE:
        names = [
            _find_player_name(state, uid) for uid in vote_event.related_user_ids
        ]
        candidates_text = ", ".join(names) if names else "несколько игроков"
        votes_count = vote_event.payload.get("votes_count")

        text = (
            f"{header}Голоса разделились между: <b>{candidates_text}</b>.\n"
            "Сегодня никто не покинул город."
        )
        if isinstance(votes_count, int):
            text += f"\n\nГолосов у лидеров: {votes_count}"
        return text

    if vote_event.type == GameEventType.DAY_VOTE_NO_VOTES:
        return (
            f"{header}Город так и не пришёл к решению.\n"
            "Сегодня никто не покинул город."
        )

    return None
