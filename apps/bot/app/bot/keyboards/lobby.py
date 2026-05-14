from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.bot.callbacks import LobbyCallback


def build_lobby_keyboard() -> InlineKeyboardMarkup:
    """Builds the lobby keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Join ✅", callback_data=LobbyCallback.JOIN)
    builder.button(text="Leave ❌", callback_data=LobbyCallback.LEAVE)
    builder.button(text="Start 🚀", callback_data=LobbyCallback.START)
    builder.button(text="Cancel ⚠️", callback_data=LobbyCallback.CANCEL)
    builder.adjust(2)
    return builder.as_markup()
