from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from app.bot.keyboards.night_action import build_night_action_keyboard
from app.bot.renderers.night_action import render_night_action_dm
from app.core.game.actions import get_allowed_night_actions
from app.core.game.roles import RoleId
from app.core.game.schemas import GameState, PlayerState


async def send_night_action_menu_for_player(
    bot: Bot,
    state: GameState,
    player: PlayerState,
) -> bool:
    """
    Sends night action menu to one player if their role has active night actions.
    Returns True if a menu was sent successfully or if there was nothing to send.
    Returns False only if sending failed for an active role.
    """
    if player.role is None:
        return True

    try:
        role_id = RoleId(player.role)
    except ValueError:
        # Invalid role is considered a failure in this context
        return False

    allowed_actions = get_allowed_night_actions(role_id)
    if not allowed_actions or not player.is_alive:
        # No actions to send, so not a failure
        return True

    # For MVP, we only send the first allowed action menu if there are many.
    # Usually there's only one.
    action_type = list(allowed_actions)[0]

    try:
        await bot.send_message(
            chat_id=player.telegram_id,
            text=render_night_action_dm(action_type),
            reply_markup=build_night_action_keyboard(state, player, action_type),
            parse_mode="HTML",
        )
        return True
    except (TelegramForbiddenError, TelegramAPIError):
        return False


async def send_night_action_menus(
    bot: Bot,
    state: GameState,
) -> set[int]:
    """
    Sends night action menus to all active-role players.
    Returns telegram_ids of players for whom sending failed.
    """
    failed_ids = set()
    for player in state.players:
        success = await send_night_action_menu_for_player(bot, state, player)
        if not success:
            failed_ids.add(player.telegram_id)

    return failed_ids
