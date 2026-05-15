from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import DayVoteCallback
from app.core.game.schemas import GameState, PlayerState


def get_available_day_vote_targets(
    state: GameState,
    voter_telegram_id: int | None = None,
) -> list[PlayerState]:
    """Returns alive players that can be voted for."""
    targets = [p for p in state.players if p.is_alive]

    if voter_telegram_id is not None:
        targets = [p for p in targets if p.telegram_id != voter_telegram_id]

    return targets


def build_day_vote_keyboard(
    state: GameState,
) -> InlineKeyboardMarkup:
    """Builds a keyboard with alive players for voting."""
    targets = get_available_day_vote_targets(state)

    buttons: list[list[InlineKeyboardButton]] = []
    # 2 buttons per row for better mobile UI
    row: list[InlineKeyboardButton] = []
    for player in targets:
        callback_data = DayVoteCallback(
            version=state.version,
            target_telegram_id=player.telegram_id,
        ).pack()
        button = InlineKeyboardButton(
            text=player.display_name,
            callback_data=callback_data,
        )
        row.append(button)
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
