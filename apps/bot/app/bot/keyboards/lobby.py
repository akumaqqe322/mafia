from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.bot.callbacks import LobbyCallback


def build_lobby_keyboard(invite_url: str | None = None) -> InlineKeyboardMarkup:
    """Builds the lobby keyboard."""
    builder = InlineKeyboardBuilder()
    if invite_url:
        builder.button(text="Join ✅", url=invite_url)
    else:
        builder.button(text="Join ✅", callback_data=LobbyCallback.JOIN.value)
    builder.button(text="Leave ❌", callback_data=LobbyCallback.LEAVE.value)
    builder.button(text="Start 🚀", callback_data=LobbyCallback.START.value)
    builder.button(text="Cancel ⚠️", callback_data=LobbyCallback.CANCEL.value)
    builder.adjust(2)
    return builder.as_markup()
