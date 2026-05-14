from uuid import uuid4

from aiogram import F, Router, types
from aiogram.filters import Command

from app.bot.callbacks import LobbyCallback
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.renderers.lobby import render_lobby
from app.core.game.engine import (
    GameAlreadyExistsError,
    GameFullError,
    GameNotFoundError,
    InvalidGamePhaseError,
    PlayerAlreadyInGameError,
    PlayerNotInGameError,
)
from app.infrastructure.container import Container

router = Router()


@router.message(Command("game"))
async def cmd_game(message: types.Message, container: Container) -> None:
    """Handles /game command to create a lobby."""
    if not message.chat or message.chat.type not in ("group", "supergroup"):
        await message.answer("Please use this command in a group chat.")
        return

    if not message.from_user:
        return

    tg_chat_id = message.chat.id

    async with container.db.get_session() as session:
        chat_repo = container.get_chat_repository(session)
        user_repo = container.get_user_repository(session)

        chat = await chat_repo.get_or_create(
            telegram_chat_id=tg_chat_id,
            title=message.chat.title,
            chat_type=message.chat.type,
        )
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await session.commit()

        game_id = uuid4()
        try:
            state = await container.game_engine.create_game(
                game_id=game_id,
                chat_id=chat.id,
                telegram_chat_id=tg_chat_id,
            )
            # Auto join creator
            display_name = (
                user.username
                or user.first_name
                or f"User {user.telegram_id}"
            )
            state = await container.game_engine.join_game(
                game_id=game_id,
                user_id=user.id,
                telegram_id=user.telegram_id,
                display_name=display_name,
            )

            await message.answer(
                render_lobby(state),
                reply_markup=build_lobby_keyboard(),
                parse_mode="HTML",
            )
        except GameAlreadyExistsError:
            await message.answer("An active game already exists in this chat!")


@router.callback_query(F.data == LobbyCallback.JOIN)
async def handle_join(callback: types.CallbackQuery, container: Container) -> None:
    if not callback.message or not callback.from_user:
        return

    tg_chat_id = callback.message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )

    if not active_game_id:
        await callback.answer("No active game found.", show_alert=True)
        return

    async with container.db.get_session() as session:
        user_repo = container.get_user_repository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        await session.commit()

    try:
        display_name = (
            user.username
            or user.first_name
            or f"User {user.telegram_id}"
        )
        state = await container.game_engine.join_game(
            game_id=active_game_id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            display_name=display_name,
        )
        await callback.message.edit_text(
            render_lobby(state),
            reply_markup=build_lobby_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer("You joined the game!")
    except PlayerAlreadyInGameError:
        await callback.answer("You are already in the game!", show_alert=True)
    except GameFullError:
        await callback.answer("Game is full!", show_alert=True)
    except GameNotFoundError:
        await callback.answer("Game not found.", show_alert=True)


@router.callback_query(F.data == LobbyCallback.LEAVE)
async def handle_leave(callback: types.CallbackQuery, container: Container) -> None:
    if not callback.message or not callback.from_user:
        return

    tg_chat_id = callback.message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )

    if not active_game_id:
        await callback.answer("No active game found.", show_alert=True)
        return

    async with container.db.get_session() as session:
        user_repo = container.get_user_repository(session)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("You are not in the game!", show_alert=True)
            return

    try:
        state = await container.game_engine.leave_game(
            game_id=active_game_id,
            user_id=user.id,
        )
        await callback.message.edit_text(
            render_lobby(state),
            reply_markup=build_lobby_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer("You left the game.")
    except PlayerNotInGameError:
        await callback.answer("You are not in the game!", show_alert=True)
    except InvalidGamePhaseError:
        await callback.answer("You can only leave during lobby phase!", show_alert=True)
    except GameNotFoundError:
        await callback.answer("Game not found.", show_alert=True)


@router.callback_query(F.data == LobbyCallback.CANCEL)
async def handle_cancel(callback: types.CallbackQuery, container: Container) -> None:
    if not callback.message:
        return

    # TODO: restrict to creator or admin
    tg_chat_id = callback.message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )

    if not active_game_id:
        await callback.answer("No active game found.", show_alert=True)
        return

    await container.game_engine.cancel_game(active_game_id)
    await callback.message.edit_text("🚫 Game canceled.")
    await callback.answer("Game canceled.")


@router.callback_query(F.data == LobbyCallback.START)
async def handle_start(callback: types.CallbackQuery) -> None:
    await callback.answer("Start will be added in the next stage! 🚀", show_alert=True)
