from aiogram import Bot, F, Router, types

from app.bot.callbacks import AdminAction, AdminCallback
from app.bot.keyboards.admin_panel import build_admin_panel_keyboard
from app.bot.renderers.admin_panel import render_admin_panel
from app.bot.services.permissions import is_group_admin
from app.core.game.schemas import GameState
from app.infrastructure.container import Container

router = Router()


def _get_callback_message(callback: types.CallbackQuery) -> types.Message | None:
    if isinstance(callback.message, types.Message):
        return callback.message
    return None


async def _get_active_state_by_chat(
    container: Container,
    telegram_chat_id: int,
) -> GameState | None:
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        telegram_chat_id
    )
    if not active_game_id:
        return None

    return await container.game_repository.get(active_game_id)


async def _is_admin_user(
    bot: Bot | None,
    chat_id: int,
    telegram_id: int,
) -> bool:
    if bot is None:
        return False
    return await is_group_admin(bot, chat_id, telegram_id)


@router.message(F.text == "/admin_game")
async def cmd_admin_game(
    message: types.Message,
    container: Container,
    bot: Bot,
) -> None:
    if message.chat.type == "private":
        await message.answer("Эта команда доступна только в групповом чате.")
        return

    if message.from_user is None:
        return

    if not await _is_admin_user(bot, message.chat.id, message.from_user.id):
        await message.answer("Панель управления доступна только администраторам чата.")
        return

    state = await _get_active_state_by_chat(container, message.chat.id)

    await message.answer(
        render_admin_panel(state),
        parse_mode="HTML",
        reply_markup=build_admin_panel_keyboard(state),
    )


@router.callback_query(F.data.startswith("adm:"))
async def handle_admin_callback(
    callback: types.CallbackQuery,
    container: Container,
    bot: Bot,
) -> None:
    if not callback.from_user:
        return

    if callback.data is None:
        await callback.answer("Некорректная команда панели.", show_alert=True)
        return

    parsed = AdminCallback.parse(callback.data)
    if parsed is None:
        await callback.answer("Некорректная команда панели.", show_alert=True)
        return

    message = _get_callback_message(callback)
    if message is None:
        await callback.answer("Это сообщение панели больше недоступно.", show_alert=True)
        return

    if not await _is_admin_user(bot, message.chat.id, callback.from_user.id):
        await callback.answer(
            "Панель управления доступна только администраторам чата.",
            show_alert=True,
        )
        return

    if parsed.action != AdminAction.REFRESH:
        # Destructive admin actions are intentionally disabled in this MVP step.
        await callback.answer(
            "Это действие пока недоступно.",
            show_alert=True,
        )
        return

    state = await _get_active_state_by_chat(container, message.chat.id)

    await message.edit_text(
        render_admin_panel(state),
        parse_mode="HTML",
        reply_markup=build_admin_panel_keyboard(state),
    )

    await callback.answer("Панель обновлена.", show_alert=False)
