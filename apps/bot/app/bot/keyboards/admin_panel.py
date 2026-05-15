from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import AdminAction, AdminCallback
from app.core.game.schemas import GamePhase, GameState


def build_admin_panel_keyboard(state: GameState | None) -> InlineKeyboardMarkup:
    """Builds the main admin panel keyboard based on game state."""
    buttons: list[list[InlineKeyboardButton]] = []

    if state is None:
        buttons.append([
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=AdminCallback(action=AdminAction.REFRESH).pack(),
            )
        ])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    # Always show refresh on top or bottom
    refresh_button = InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data=AdminCallback(action=AdminAction.REFRESH).pack(),
    )

    if state.phase == GamePhase.LOBBY:
        buttons.append([
            InlineKeyboardButton(
                text="👥 Игроки / кик",
                callback_data=AdminCallback(
                    action=AdminAction.KICK_LIST,
                    version=state.version,
                ).pack(),
            )
        ])
        buttons.append([refresh_button])

    elif state.phase in (GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTING):
        buttons.append([
            InlineKeyboardButton(
                text="⏭ Завершить фазу",
                callback_data=AdminCallback(
                    action=AdminAction.TICK,
                    version=state.version,
                ).pack(),
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🚫 Завершить игру",
                callback_data=AdminCallback(
                    action=AdminAction.FINISH,
                    version=state.version,
                ).pack(),
            )
        ])
        buttons.append([refresh_button])

    elif state.phase == GamePhase.FINISHED:
        buttons.append([refresh_button])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_admin_kick_keyboard(state: GameState) -> InlineKeyboardMarkup:
    """Builds a keyboard with players for kicking from lobby."""
    buttons: list[list[InlineKeyboardButton]] = []

    row: list[InlineKeyboardButton] = []
    for player in state.players:
        callback_data = AdminCallback(
            action=AdminAction.KICK,
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

    # Back button
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=AdminCallback(action=AdminAction.BACK).pack(),
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_admin_finish_confirmation_keyboard(state: GameState) -> InlineKeyboardMarkup:
    """Builds the force finish confirmation keyboard."""
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="⚠️ Да, остановить игру",
                callback_data=AdminCallback(
                    action=AdminAction.CONFIRM_FINISH,
                    version=state.version,
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=AdminCallback(action=AdminAction.BACK).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
