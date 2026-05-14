from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from app.core.game.schemas import GameState

def is_lobby_creator(state: GameState, telegram_id: int) -> bool:
    """Returns True if the user is the one who created the lobby."""
    if state.creator_telegram_id is None:
        return False
    return state.creator_telegram_id == telegram_id

async def is_group_admin(bot: Bot, chat_id: int, telegram_id: int) -> bool:
    """Checks if the user is a creator or administrator of the group chat."""
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=telegram_id)
        return member.status in {"creator", "administrator"}
    except (TelegramAPIError, TelegramForbiddenError):
        # Fallback to False if we can't check permissions (e.g. bot kicked or user left)
        return False

async def can_manage_game(bot: Bot, state: GameState, telegram_id: int) -> bool:
    """
    Returns True if the user has permission to manage the lobby/game (e.g. Start/Cancel).
    Managers are:
    1. Lobby creator
    2. Group administrators/creators
    """
    if is_lobby_creator(state, telegram_id):
        return True
    
    return await is_group_admin(bot, state.telegram_chat_id, telegram_id)
