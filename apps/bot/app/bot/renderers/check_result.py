import html
from uuid import UUID

from app.core.game.events import EventVisibility, GameEvent, GameEventType
from app.core.game.schemas import GameState


def _find_player_name(state: GameState, user_id: UUID) -> str:
    """Finds a player by user_id and returns their escaped display name."""
    player = next((p for p in state.players if p.user_id == user_id), None)
    if player:
        return html.escape(player.display_name)
    return "неизвестный игрок"


def render_check_result(state: GameState, event: GameEvent) -> str | None:
    """
    Renders the private result of a night check (Sheriff/Don).
    Returns None if the event is not a private CHECK_RESULT or payload is invalid.
    """
    if event.type != GameEventType.CHECK_RESULT:
        return None

    if event.visibility != EventVisibility.PRIVATE:
        return None

    if event.target_user_id is None:
        return None

    is_mafia = event.payload.get("is_mafia")
    if type(is_mafia) is not bool:
        return None

    target_name = _find_player_name(state, event.target_user_id)

    header = "🔎 <b>Результат проверки</b>\n\n"

    if is_mafia:
        return f"{header}Игрок <b>{target_name}</b> связан с мафией."
    else:
        return f"{header}Игрок <b>{target_name}</b> не связан с мафией."
