from uuid import UUID

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from app.bot.callbacks import AdminAction, AdminCallback
from app.bot.keyboards.admin_panel import (
    build_admin_kick_keyboard,
    build_admin_panel_keyboard,
)
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.renderers.admin_panel import (
    render_admin_kick_panel,
    render_admin_panel,
)
from app.bot.renderers.lobby import render_lobby
from app.bot.services.permissions import is_group_admin
from app.bot.utils import build_join_url
from app.core.game.engine import (
    GameNotFoundError,
    InvalidGamePhaseError,
    PlayerNotInGameError,
)
from app.core.game.schemas import GamePhase, GameState, PlayerState
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


def _find_player_by_telegram_id(
    state: GameState,
    telegram_id: int,
) -> PlayerState | None:
    return next((p for p in state.players if p.telegram_id == telegram_id), None)


async def _update_lobby_message_if_possible(
    message: types.Message,
    container: Container,
    state: GameState,
    game_id: UUID,
) -> None:
    if state.lobby_message_id is None or message.bot is None:
        return

    try:
        # Re-generate invite URL
        token = await container.game_invite_repository.create_invite(game_id)
        bot_info = await message.bot.get_me()
        invite_url = build_join_url(bot_info.username or "mafia_bot", token)

        await message.bot.edit_message_text(
            chat_id=state.telegram_chat_id,
            message_id=state.lobby_message_id,
            text=render_lobby(state),
            reply_markup=build_lobby_keyboard(invite_url),
            parse_mode="HTML",
        )
    except (TelegramAPIError, TelegramForbiddenError):
        # Silently ignore editing errors (e.g. message too old or deleted)
        pass


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

    state = await _get_active_state_by_chat(container, message.chat.id)

    if parsed.action in (AdminAction.REFRESH, AdminAction.BACK):
        await message.edit_text(
            render_admin_panel(state),
            parse_mode="HTML",
            reply_markup=build_admin_panel_keyboard(state),
        )
        await callback.answer("Панель обновлена.", show_alert=False)
        return

    if parsed.action == AdminAction.KICK_LIST:
        if state is None:
            await message.edit_text(
                render_admin_panel(None),
                parse_mode="HTML",
                reply_markup=build_admin_panel_keyboard(None),
            )
            await callback.answer("Активная игра не найдена.", show_alert=True)
            return

        if state.phase != GamePhase.LOBBY:
            await callback.answer(
                "Кик игроков доступен только до начала игры.",
                show_alert=True,
            )
            return

        if parsed.version != state.version:
            await callback.answer(
                "Панель устарела. Обновите /admin_game.",
                show_alert=True,
            )
            return

        await message.edit_text(
            render_admin_kick_panel(state),
            parse_mode="HTML",
            reply_markup=build_admin_kick_keyboard(state),
        )
        await callback.answer("Выберите игрока.", show_alert=False)
        return

    if parsed.action == AdminAction.KICK:
        if state is None:
            await message.edit_text(
                render_admin_panel(None),
                parse_mode="HTML",
                reply_markup=build_admin_panel_keyboard(None),
            )
            await callback.answer("Активная игра не найдена.", show_alert=True)
            return

        if state.phase != GamePhase.LOBBY:
            await callback.answer(
                "Кик игроков доступен только до начала игры.",
                show_alert=True,
            )
            return

        if parsed.version != state.version:
            await callback.answer(
                "Панель устарела. Обновите /admin_game.",
                show_alert=True,
            )
            return

        if parsed.target_telegram_id is None:
            await callback.answer("Некорректный игрок для кика.", show_alert=True)
            return

        target = _find_player_by_telegram_id(state, parsed.target_telegram_id)
        if target is None:
            await callback.answer("Игрок уже не находится в лобби.", show_alert=True)
            return

        active_game_id = await container.active_game_registry.get_active_game_by_chat(
            message.chat.id
        )
        if not active_game_id:
            await callback.answer("Активная игра не найдена.", show_alert=True)
            return

        try:
            updated_state = await container.game_engine.leave_game(
                game_id=active_game_id,
                user_id=target.user_id,
            )
            await container.player_game_repository.clear_active_game(target.telegram_id)
        except PlayerNotInGameError:
            await callback.answer("Игрок уже не находится в лобби.", show_alert=True)
            return
        except InvalidGamePhaseError:
            await callback.answer(
                "Кик игроков доступен только до начала игры.",
                show_alert=True,
            )
            return
        except GameNotFoundError:
            await callback.answer("Игра не найдена.", show_alert=True)
            return

        await _update_lobby_message_if_possible(
            message=message,
            container=container,
            state=updated_state,
            game_id=active_game_id,
        )

        await message.edit_text(
            render_admin_kick_panel(updated_state),
            parse_mode="HTML",
            reply_markup=build_admin_kick_keyboard(updated_state),
        )

        await callback.answer(
            f"Игрок {target.display_name} удалён из лобби.",
            show_alert=False,
        )
        return

    # Phase control actions are intentionally disabled in this MVP step.
    await callback.answer(
        "Это действие пока недоступно.",
        show_alert=True,
    )
